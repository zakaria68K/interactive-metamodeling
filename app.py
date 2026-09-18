import datetime
import html
import json
import queue
import re
import sys
import threading
import uuid
from pathlib import Path

import gradio as gr
from pypdf import PdfReader

from metaLoop.llm_client import LLMClient
from metaLoop.metamodeling_agent import MetamodelingAgent
from metaLoop.imageGeneration.jjscript_to_image import parse_jjscript, build_svg
from metaLoop.baselineApproaches.direct_generation import generate_direct
from app_modules.quiz import DOMAINS, _compute_form_score
from app_modules.profile import _load_user_profile, _save_user_profile
from app_modules.svg_utils import _to_svg
from app_modules.data_logger import log_quiz, log_session


# ── Color palette ──────────────────────────────────────────────────────────────
_COLORS = [
    "#FFD700","#90EE90","#87CEEB","#FFB6C1","#DDA0DD",
    "#F0E68C","#98FB98","#ADD8E6","#FFA07A","#20B2AA",
    "#FF8C00","#9370DB","#3CB371","#DC143C","#00CED1",
]


def _show_profile_page(username: str):
    # The post-use questionnaire for a domain only ever appears once that
    # participant's profile shows they've actually completed a run (see
    # "tool_completed", set by _save_session and run_oneshot) — never right
    # after submitting the pre-use questionnaire, and never for the domain
    # they aren't assigned to. Once it does appear, the pre-use form for
    # that domain is hidden — only one of the two is ever shown at a time.
    profile = _load_user_profile(username) if (username or "").strip() else {}
    domain = profile.get("domain", "")
    tool_completed = bool(profile.get("tool_completed"))
    return (
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=True),
        gr.update(visible=domain == "bp" and not tool_completed),
        gr.update(visible=domain == "engine" and not tool_completed),
        gr.update(visible=domain == "bp" and tool_completed),
        gr.update(visible=domain == "engine" and tool_completed),
    )


def _show_tool_page(domain: str):
    # Pre-fill the domain prompt with its fixed description (User-study.md:
    # every participant in a domain builds the same metamodel) but leave it
    # editable — the participant can tweak it if they want to.
    prompt_update = gr.update()
    if domain in DOMAINS:
        prompt_update = gr.update(value=DOMAINS[domain]["prompt"], interactive=True)

    return (
        gr.update(visible=True),
        gr.update(visible=True),
        gr.update(visible=True),
        gr.update(visible=True),
        gr.update(visible=False),
        prompt_update,
    )


def _save_user_name(name: str, domain: str, consent: bool):
    username = (name or "").strip()
    _HIDE_ALL_FORMS = (gr.update(visible=False),) * 4

    if not consent:
        return ("**Current participant:** None", "⚠️ Please confirm your consent to participate before continuing.", "", "") + _HIDE_ALL_FORMS
    if not username:
        return ("**Current participant:** None", "⚠️ Participant ID is required.", "", "") + _HIDE_ALL_FORMS
    if domain not in DOMAINS:
        return ("**Current participant:** None", "⚠️ Please select a study domain first.", "", "") + _HIDE_ALL_FORMS

    _save_user_profile(username, extra={"domain": domain, "consent": True})
    status = f"Profile saved for participant {html.escape(username)}. You may now complete the pre-use questionnaire."
    return (
        f"**Current participant:** {html.escape(username)}",
        status,
        username,
        domain,
        gr.update(visible=domain == "bp"),
        gr.update(visible=domain == "engine"),
        gr.update(visible=False),
        gr.update(visible=False),
    )


def _make_submit_pre(domain_key: str):
    questions = DOMAINS[domain_key]["pre"]

    def handler(name: str, *answers):
        username = (name or "").strip()
        if not username:
            return "", "⚠️ Save your participant ID first.", gr.update(visible=False)

        responses = {
            question["id"]: (answers[idx] if idx < len(answers) else [])
            for idx, question in enumerate(questions)
        }
        score = _compute_form_score(responses, questions)
        _save_user_profile(username, pre_data=responses, pre_score=score)
        log_quiz(username, domain_key, "pre", responses, score)
        status = "Pre-use evaluation saved successfully."
        # The post-use questionnaire stays hidden here — it only appears once
        # the participant has actually used the tool (see _show_profile_page).
        return status, f"Saved pre-use questionnaire for {html.escape(username)}.", gr.update()

    return handler


def _make_submit_post(domain_key: str):
    questions = DOMAINS[domain_key]["post"]

    def handler(name: str, *answers):
        username = (name or "").strip()
        if not username:
            return "", "⚠️ Save your participant ID first."

        responses = {
            question["id"]: (answers[idx] if idx < len(answers) else [])
            for idx, question in enumerate(questions)
        }
        score = _compute_form_score(responses, questions)
        _save_user_profile(username, post_data=responses, post_score=score)
        log_quiz(username, domain_key, "post", responses, score)
        status = "Post-use evaluation saved successfully."
        return status, f"Saved post-use questionnaire for {html.escape(username)}."

    return handler


_submit_bp_pre_evaluation = _make_submit_pre("bp")
_submit_engine_pre_evaluation = _make_submit_pre("engine")
_submit_bp_post_evaluation = _make_submit_post("bp")
_submit_engine_post_evaluation = _make_submit_post("engine")


# SVG rendering helper moved to app_modules.svg_utils._to_svg


def _read_file(file_obj) -> tuple[str, str]:
    file_path: str | None = None
    file_name = "file"

    if hasattr(file_obj, "name"):
        file_path = file_obj.name
        file_name = getattr(file_obj, "orig_name", Path(file_obj.name).name)
    elif isinstance(file_obj, str):
        file_path = file_obj
        file_name = Path(file_obj).name
    else:
        file_path = str(file_obj)
        file_name = Path(file_path).name

    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(file_path)
        content = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    return content, file_name


# ── Session ────────────────────────────────────────────────────────────────────
class _Session:
    def __init__(self):
        self.elicit_q: queue.Queue[str] = queue.Queue()
        self.elicit_a: queue.Queue[str] = queue.Queue()
        self.waiting_elicitation: bool = False
        self.current_elicitation_question: str = ""

        self.approval_q: queue.Queue[dict] = queue.Queue()
        self.approval_a: queue.Queue[bool] = queue.Queue()
        self.waiting_approval: bool = False
        self.pending_payload: dict | None = None

        self.result_q: queue.Queue[dict] = queue.Queue()
        self.final_result: dict | None = None

        self.chat: list[dict] = []
        self.log: list[str] = []

        self.attached_file_content: str = ""
        self.attached_file_name: str = ""
        self.file_analysis: dict = {}
        self.all_concepts: list[str] = []
        self.extra_concepts: list[str] = []
        self.current_metamodel: str = ""
        self.user_name: str = ""


_sessions: dict[str, _Session] = {}


def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def _is_yes_no_question(question: str) -> bool:
    q = (question or "").strip().lower()
    if not q or "?" not in q:
        return False
    if q.startswith(("what", "how", "why", "which", "who", "where", "when")):
        return False
    if "challenge level" in q or "validation challenge" in q:
        return False
    return any(m in q for m in ["yes/no", "yes or no", "y/n", "are you", "do you", "is it", "should", "would", "can"])


def _highlight_spans(file_content: str, sentence_highlights: list[dict]) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for item in sentence_highlights:
        sentence = item.get("sentence", "").strip()
        concept = item.get("concept", "")
        if not sentence:
            continue
        pattern = r"\s+".join(re.escape(word) for word in sentence.split())
        match = re.search(pattern, file_content, re.IGNORECASE)
        if match:
            spans.append((match.start(), match.end(), concept))

    spans.sort(key=lambda span: span[0])
    merged: list[tuple[int, int, str]] = []
    for start, end, concept in spans:
        if merged and start < merged[-1][1]:
            continue
        merged.append((start, end, concept))
    return merged


def _compute_coverage_percentage(file_content: str, spans: list[tuple[int, int, str]]) -> int:
    total_chars = sum(1 for char in file_content if not char.isspace())
    if total_chars == 0:
        return 0

    covered_chars = 0
    for start, end, _concept in spans:
        covered_chars += sum(1 for char in file_content[start:end] if not char.isspace())

    return round((covered_chars / total_chars) * 100)


def _format_elicitation_question(question: str, context: dict) -> str:
    if context.get("validation_stage") != "challenge_selection":
        return question

    concept = str(context.get("current_concept", "")).strip()
    if not concept:
        return question

    return f"Validation challenge for **{concept}**\n\n{question}"


# ── Coverage analysis ──────────────────────────────────────────────────────────
def _run_coverage_analysis(file_content: str, concepts: list[str], metamodel: str) -> dict:
    client = LLMClient()

    modeled = re.findall(
        r"create\s+(?:abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)", metamodel, re.IGNORECASE
    )
    modeled_lower = {m.lower() for m in modeled}
    modeled_str = ", ".join(modeled) if modeled else "(none yet)"
    not_yet_modeled = [c for c in concepts if c.lower() not in modeled_lower]

    prompt = (
        "You are a domain model analyst.\n\n"
        f"Currently modeled concepts: {modeled_str}\n\n"
        f"Current metamodel:\n{metamodel}\n\n"
        f"Document:\n{file_content}\n\n"
        "Tasks:\n"
        "1. For each sentence in the document that relates to a CURRENTLY MODELED concept, "
        "record it in sentence_highlights with the matching concept name.\n"
        f"2. Identify domain concepts found in the document that are NOT in this full list: "
        + (", ".join(concepts) if concepts else "(none)") + "\n\n"
        "Return ONLY valid JSON with these keys:\n"
        "  sentence_highlights: array of {{sentence: string, concept: string}}\n"
        "  new_concepts: array of concept names found in doc but NOT in the full list above\n"
    )

    result = client.invoke_json(prompt)
    coverage_spans = _highlight_spans(file_content, result.get("sentence_highlights", []))
    result["coverage_percentage"] = _compute_coverage_percentage(file_content, coverage_spans)
    result["not_yet_modeled"] = not_yet_modeled
    result["modeled_concepts"] = modeled
    return result


def _build_coverage_html(file_content: str, analysis: dict, all_concepts: list[str]) -> str:
    not_yet_modeled = analysis.get("not_yet_modeled", [])
    new_concepts    = analysis.get("new_concepts", [])
    coverage_pct    = analysis.get("coverage_percentage", 0)
    modeled         = analysis.get("modeled_concepts", [])
    sentence_highlights = analysis.get("sentence_highlights", [])

    merged = _highlight_spans(file_content, sentence_highlights)
    coverage_pct = _compute_coverage_percentage(file_content, merged)

    parts: list[str] = []
    pos = 0
    for start, end, concept in merged:
        parts.append(html.escape(file_content[pos:start]))
        parts.append(
            f'<mark style="background:#bbf7d0;border-radius:4px;padding:1px 4px;font-weight:500;" '
            f'title="&#10003; {html.escape(concept)}">'
            f'{html.escape(file_content[start:end])}</mark>'
        )
        pos = end
    parts.append(html.escape(file_content[pos:]))
    escaped = "".join(parts)

    bar_pct   = min(max(coverage_pct, 0), 100)
    bar_color = "#22c55e" if bar_pct >= 70 else "#f59e0b" if bar_pct >= 40 else "#ef4444"

    modeled_chips = "".join(
        f'<span style="display:inline-block;background:#dcfce7;color:#15803d;border:1px solid #86efac;'
        f'border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;margin:3px 3px 3px 0">'
        f'&#10003; {html.escape(c)}</span>'
        for c in modeled
    ) if modeled else '<span style="color:#9ca3af;font-size:13px">None modeled yet</span>'

    pending_chips = "".join(
        f'<span style="display:inline-block;background:#fef9c3;color:#92400e;border:1px solid #fcd34d;'
        f'border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;margin:3px 3px 3px 0">'
        f'&#9679; {html.escape(c)}</span>'
        for c in not_yet_modeled
    ) if not_yet_modeled else '<span style="color:#9ca3af;font-size:13px">All concepts modeled</span>'

    new_chips = "".join(
        f'<span style="display:inline-block;background:#dbeafe;color:#1e40af;border:1px solid #93c5fd;'
        f'border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;margin:3px 3px 3px 0">'
        f'+ {html.escape(c)}</span>'
        for c in new_concepts
    ) if new_concepts else '<span style="color:#9ca3af;font-size:13px">None discovered</span>'

    return f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1f2937">
  <div style="display:flex;align-items:center;gap:20px;background:#f8fafc;border:1px solid #e2e8f0;
              border-radius:12px;padding:16px 20px;margin-bottom:18px">
    <div style="text-align:center;min-width:72px">
      <div style="font-size:38px;font-weight:800;line-height:1;color:{bar_color}">{coverage_pct}%</div>
      <div style="font-size:11px;color:#6b7280;margin-top:2px;text-transform:uppercase;letter-spacing:.05em">covered</div>
      <div style="margin-top:6px;background:#e5e7eb;border-radius:99px;height:5px;width:60px;margin-left:auto;margin-right:auto">
        <div style="background:{bar_color};border-radius:99px;height:5px;width:{bar_pct}%"></div>
      </div>
    </div>
    <div style="flex:1">
      <div style="font-size:12px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Legend</div>
      <div style="display:flex;flex-wrap:wrap;gap:14px">
        <span style="display:flex;align-items:center;gap:6px;font-size:13px;color:#374151">
          <span style="display:inline-block;width:14px;height:14px;background:#bbf7d0;border-radius:3px;border:1px solid #4ade80"></span>
          Modeled in current metamodel
        </span>
        <span style="display:flex;align-items:center;gap:6px;font-size:13px;color:#374151">
          <span style="display:inline-block;width:14px;height:14px;background:#f3f4f6;border-radius:3px;border:1px solid #d1d5db"></span>
          Not yet covered
        </span>
      </div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:18px">
    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:14px">
      <div style="font-size:11px;font-weight:700;color:#15803d;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">&#10003; Modeled so far</div>
      <div>{modeled_chips}</div>
    </div>
    <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:14px">
      <div style="font-size:11px;font-weight:700;color:#92400e;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">&#9679; Pending modeling</div>
      <div>{pending_chips}</div>
    </div>
    <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:14px">
      <div style="font-size:11px;font-weight:700;color:#1e40af;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">+ New in document</div>
      <div>{new_chips}</div>
    </div>
  </div>
  <div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
    <div style="background:#f8fafc;padding:10px 16px;font-size:12px;font-weight:600;color:#6b7280;
                text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #e2e8f0">
      Document &mdash; hover <span style="background:#bbf7d0;border-radius:3px;padding:1px 5px;color:#15803d">green</span> passages for concept name
    </div>
    <div style="max-height:480px;overflow-y:auto;padding:18px 20px;background:#ffffff;
                line-height:1.9;white-space:pre-wrap;font-size:13.5px;color:#374151">{escaped}</div>
  </div>
</div>
"""


# ── Agent thread ───────────────────────────────────────────────────────────────
def _run_agent(sess: _Session, prompt: str) -> None:
    agent = MetamodelingAgent()

    def user_responder(question: str, context: dict) -> str:
        if context.get("validation_stage") == "file_new_concepts_selection":
            sess.log.append(f"[{_ts()}] File concept suggestions handled via coverage checkbox UI.")
            return "none"

        if context.get("validation_stage") == "challenge_selection":
            formatted_question = _format_elicitation_question(question, context)
            sess.chat.append({"role": "assistant", "content": formatted_question})
            sess.waiting_elicitation = True
            sess.current_elicitation_question = formatted_question
            sess.elicit_q.put(formatted_question)
            answer = sess.elicit_a.get(block=True)
            sess.waiting_elicitation = False
            sess.current_elicitation_question = ""
            sess.chat.append({"role": "user", "content": answer})
            return answer

        if "proposed_concepts" in context:
            raw = context.get("proposed_concepts_raw")
            if raw and isinstance(raw, list) and isinstance(raw[0], dict):
                lines = [
                    f"* **{c.get('name','')}**: {c.get('description','')}"
                    if c.get("description") else f"* {c.get('name','')}"
                    for c in raw
                ]
                sess.all_concepts = [c.get("name", "") for c in raw if c.get("name")]
            else:
                concepts = context.get("proposed_concepts", [])
                lines = [f"* {c}" for c in concepts]
                sess.all_concepts = list(concepts)
            sess.chat.append({
                "role": "assistant",
                "content": "**Proposed concepts:**\n" + "\n".join(lines),
            })

        sess.chat.append({"role": "assistant", "content": question})
        sess.log.append(f"[{_ts()}] Q: {question[:80]}")
        sess.waiting_elicitation = True
        sess.current_elicitation_question = question
        sess.elicit_q.put(question)
        answer = sess.elicit_a.get(block=True)
        sess.waiting_elicitation = False
        sess.current_elicitation_question = ""
        sess.chat.append({"role": "user", "content": answer})
        return answer

    def human_validator(payload: dict) -> bool | dict:
        sess.log.append(f"[{_ts()}] Review: {payload.get('concept', '')}")
        sess.pending_payload = payload
        if payload.get("chunk"):
            sess.current_metamodel = payload["chunk"]
            sess.file_analysis = {}
        sess.waiting_approval = True
        sess.approval_q.put(payload)
        decision = sess.approval_a.get(block=True)
        sess.waiting_approval = False

        approved = True
        feedback = ""
        if isinstance(decision, dict):
            approved = bool(decision.get("approved", False))
            feedback = str(decision.get("feedback", "")).strip()
        else:
            approved = bool(decision)

        sess.log.append(f"[{_ts()}] {'OK' if approved else 'X'} {payload.get('concept', '')}")
        if feedback:
            sess.log.append(f"[{_ts()}] Rejection feedback: {feedback}")
            sess.pending_payload["rejection_feedback"] = feedback
        return {"approved": approved, "feedback": feedback} if feedback else approved

    try:
        initial_state = (
            {"attached_file_content": sess.attached_file_content}
            if sess.attached_file_content else {}
        )
        domain = _load_user_profile(sess.user_name).get("domain", "") if sess.user_name else ""
        if DOMAINS.get(domain, {}).get("concepts"):
            initial_state["required_concepts"] = DOMAINS[domain]["concepts"]
        result = agent.run_iterative(
            prompt,
            human_validator=human_validator,
            user_responder=user_responder,
            initial_state=initial_state,
        )
        sess.log.append(f"[{_ts()}] Done.")

        while sess.extra_concepts:
            extra = sess.extra_concepts[:]
            sess.extra_concepts = []
            sess.log.append(f"[{_ts()}] Extra round: {len(extra)} concept(s) — {', '.join(extra)}")
            seed = {
                "user_prompt": prompt,
                "attached_file_content": sess.attached_file_content,
                "intent_summary": result.get("intent_summary", ""),
                "approved_chunks": result.get("approved_chunks", []),
                "cumulative_sample_model": result.get("cumulative_sample_model", ""),
            }
            result = agent.run_extra_concepts(
                extra, seed,
                human_validator=human_validator,
                user_responder=user_responder,
            )
            sess.log.append(f"[{_ts()}] Extra round done.")

        if result.get("cumulative_sample_model"):
            sess.chat.append({
                "role": "assistant",
                "content": f"**Final instance model:**\n```\n{result['cumulative_sample_model']}\n```",
            })
        if result.get("final_metamodel"):
            sess.current_metamodel = result["final_metamodel"]
            sess.file_analysis = {}
        _save_session(sess, result)
        sess.result_q.put(result)
    except Exception as exc:
        sess.log.append(f"[{_ts()}] Error: {exc}")
        sess.result_q.put({"final_metamodel": f"# ERROR\n{exc}", "concepts": []})


def _save_session(sess: _Session, result: dict) -> None:
    out_dir = Path("session_logs")
    out_dir.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    data = {
        "timestamp": ts,
        "method": "interactive",
        "user": sess.user_name,
        "domain": _load_user_profile(sess.user_name).get("domain", "") if sess.user_name else "",
        "log": sess.log,
        "concepts": result.get("concepts", []),
        "final_metamodel": result.get("final_metamodel", ""),
        "final_sample_model": result.get("cumulative_sample_model", ""),
        "final_validation": result.get("final_validation", {}),
    }
    (out_dir / f"session_{ts}.json").write_text(json.dumps(data, indent=2))
    log_session(data)  # also pushed off-Space; local session_logs/ alone won't survive a Space restart
    if sess.user_name:
        _save_user_profile(sess.user_name, extra={"tool_completed": True})


# ── Event handlers (ALL LOGIC UNCHANGED) ──────────────────────────────────────
def start(prompt: str, sid: str, user_name: str):
    _EMPTY = (sid, [], "", gr.update(visible=False), gr.update(visible=False),
              gr.update(visible=False), gr.update(visible=False),
              gr.update(), gr.update(), gr.update(value="Enter a prompt first."), "")
    if not prompt.strip():
        return _EMPTY

    if not (user_name or "").strip():
        current_chat = _sessions[sid].chat if sid and sid in _sessions else []
        return (
            sid,
            list(current_chat),
            "",
            gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            gr.update(), gr.update(), gr.update(value="⚠️ Please save your profile in User Setup before starting."), ""
        )

    if _load_user_profile(user_name).get("used_one_shot"):
        current_chat = _sessions[sid].chat if sid and sid in _sessions else []
        return (
            sid,
            list(current_chat),
            "",
            gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            gr.update(), gr.update(),
            gr.update(value="⚠️ This profile already used the one-shot (control) mode — the interactive tool is disabled for this study session."),
            "",
        )

    new_sid = str(uuid.uuid4())
    sess = _Session()
    sess.user_name = user_name
    sess.log.append(f"[{_ts()}] Started: {prompt[:80]}")
    sess.chat.append({
        "role": "assistant",
        "content": (
            f"Starting metamodel for: **{prompt}**\n\n"
            "I will ask a few questions to understand the domain."
        ),
    })
    _sessions[new_sid] = sess
    # Mark the profile as having used the tool as soon as an interactive
    # session actually launches, rather than waiting for the full
    # concept-by-concept graph to run to completion — that graph only
    # finishes once every chunk has been approved through to the end, which
    # a participant may reasonably stop short of after genuinely using the
    # tool for a while. Gating post-quiz visibility on that full completion
    # left it unreachable in practice; gating on "started a session" is what
    # "used the tool" means for the study's between-subjects design.
    _save_user_profile(user_name, extra={"tool_completed": True})
    threading.Thread(target=_run_agent, args=(sess, prompt), daemon=True).start()

    return (new_sid, list(sess.chat), "",
            gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            gr.update(), gr.update(), gr.update(value=f"[{_ts()}] Running..."), "")


def poll(sid: str):
    _noop = tuple(gr.update() for _ in range(15))
    if not sid or sid not in _sessions:
        return _noop

    sess = _sessions[sid]
    log_text = "\n".join(sess.log[-20:])

    try:
        sess.elicit_q.get_nowait()
    except queue.Empty:
        pass
    try:
        sess.final_result = sess.result_q.get_nowait()
    except queue.Empty:
        pass

    if sess.final_result is not None:
        return (
            list(sess.chat),
            gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False),
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(),
            gr.update(value=_to_svg(sess.final_result.get("final_metamodel", ""), "Final Metamodel")),
            gr.update(value=sess.final_result.get("final_metamodel", "")),   # raw JjScript
            gr.update(value=sess.final_result.get("final_validation", {})),
            log_text,
        )

    if sess.waiting_approval and sess.pending_payload:
        p = sess.pending_payload
        return (
            list(sess.chat),
            gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=True),
            gr.update(value=f"**{p.get('concept', '')}**"),
            gr.update(value=_to_svg(
                p.get("chunk", ""),
                f"Chunk: {p.get('concept', '')}",
                highlight_names=set(p.get("highlight_names", [])) if p.get("highlight_names") else None,
            )),
            gr.update(value=p.get("chunk", "")),   # raw JjScript
            gr.update(value=_to_svg(
                p.get("sample_model", ""),
                f"Sample: {p.get('concept', '')}",
            )),
            gr.update(value=p.get("explanation", "")),
            gr.update(value=p.get("validation", {})),
            gr.update(),
            gr.update(),
            gr.update(),
            log_text,
        )
    yes_no       = _is_yes_no_question(sess.current_elicitation_question)
    is_challenge = "challenge level" in sess.current_elicitation_question.lower()
    waiting      = sess.waiting_elicitation
    return (
        list(sess.chat),
        gr.update(visible=waiting and not yes_no and not is_challenge),
        gr.update(visible=waiting and yes_no),
        gr.update(visible=waiting and is_challenge),
        gr.update(visible=False),
        gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
        gr.update(), gr.update(), gr.update(), gr.update(),
        log_text,
    )


def submit_answer(answer: str, sid: str):
    if sid in _sessions and answer.strip():
        _sessions[sid].elicit_a.put(answer.strip())
    return "", gr.update(visible=False), gr.update(visible=False)


def submit_yes_no(answer: str, sid: str):
    if sid in _sessions:
        _sessions[sid].elicit_a.put(answer)
    return gr.update(visible=False), gr.update(visible=False)


def submit_challenge_level(level: str, sid: str):
    if sid in _sessions:
        _sessions[sid].elicit_a.put(level)
    return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)


def approve(sid: str):
    if sid in _sessions:
        sess = _sessions[sid]
        sess.approval_a.put(True)
        sess.pending_rejection_feedback = ""
    return gr.update(visible=False), gr.update(visible=False)


def begin_reject_feedback(sid: str):
    if sid in _sessions:
        sess = _sessions[sid]
        sess.pending_rejection_feedback = ""
    return gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(value="")

def submit_rejection_feedback(feedback: str, sid: str):
    if sid in _sessions:
        sess = _sessions[sid]
        reason = (feedback or "").strip()
        sess.pending_rejection_feedback = reason
        sess.approval_a.put({"approved": False, "feedback": reason})
        # Confirm regeneration in chat
        sess.chat.append({
            "role": "assistant",
            "content": f"Feedback received. Regenerating chunk with your corrections...",
        })
    return gr.update(visible=False), gr.update(visible=True), gr.update(visible=True), gr.update(value="")


def attach_file(file_obj, sid: str):
    if not file_obj:
        return "No file selected.", gr.update(visible=False)
    if not sid or sid not in _sessions:
        return "No active session.", gr.update(visible=False)
    try:
        content, file_name = _read_file(file_obj)
    except Exception as e:
        return f"Error reading file: {e}", gr.update(visible=False)
    if not content.strip():
        return "File appears empty.", gr.update(visible=False)

    sess = _sessions[sid]
    sess.attached_file_content = content
    sess.attached_file_name = file_name
    sess.file_analysis = {}
    sess.log.append(f"[{_ts()}] File attached: {file_name} ({len(content)} chars)")
    return f"✓ {file_name}", gr.update(visible=True)


def open_coverage(sid: str):
    def _make_overlay(inner_html: str) -> str:
        return f"""
        <div id='cov-overlay' style='
            position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.65);
            overflow-y:auto;padding:40px 16px;box-sizing:border-box'>
          <div style='max-width:960px;margin:0 auto;background:white;border-radius:12px;padding:24px'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:16px'>
              <h2 style='margin:0;font-size:20px'>Coverage Analysis</h2>
              <button onclick="document.getElementById('cov-overlay').remove()"
                  style='background:#dc2626;color:white;border:none;border-radius:6px;
                         padding:8px 16px;font-size:13px;cursor:pointer'>&#x2715; Close</button>
            </div>
            {inner_html}
          </div>
        </div>"""

    if not sid or sid not in _sessions:
        yield gr.update(value=""), gr.update(choices=[], value=[]), gr.update(visible=False)
        return
    sess = _sessions[sid]
    if not sess.attached_file_content:
        yield gr.update(value=""), gr.update(choices=[], value=[]), gr.update(visible=False)
        return
    if not sess.all_concepts:
        yield gr.update(value=""), gr.update(choices=[], value=[]), gr.update(visible=False)
        return

    loading_html = """
        <div style='padding:60px;text-align:center;font-size:16px;color:#555'>
          <div style='font-size:40px;margin-bottom:14px'>&#9203;</div>
          Analysing document coverage&hellip;
          <br><small style='color:#999'>This may take a few seconds.</small>
        </div>"""
    yield gr.update(value=_make_overlay(loading_html)), gr.update(choices=[], value=[]), gr.update(visible=False)

    if not sess.file_analysis:
        metamodel = sess.current_metamodel or (sess.pending_payload or {}).get("chunk", "")
        sess.log.append(f"[{_ts()}] Analysing coverage...")
        try:
            sess.file_analysis = _run_coverage_analysis(
                sess.attached_file_content, sess.all_concepts, metamodel
            )
            pct  = sess.file_analysis.get("coverage_percentage", 0)
            miss = len(sess.file_analysis.get("not_yet_modeled", []))
            sess.log.append(f"[{_ts()}] Coverage: {pct}%, {miss} missing.")
        except Exception as e:
            sess.log.append(f"[{_ts()}] Analysis error: {e}")
            yield gr.update(value=""), gr.update(choices=[], value=[]), gr.update(visible=False)
            return

    coverage_html = _build_coverage_html(
        sess.attached_file_content, sess.file_analysis, sess.all_concepts
    )
    new_concepts = sess.file_analysis.get("new_concepts", [])
    has_new = bool(new_concepts)
    sess.log.append(f"[{_ts()}] Coverage rendered.")
    yield (
        gr.update(value=_make_overlay(coverage_html)),
        gr.update(choices=new_concepts, value=new_concepts),
        gr.update(visible=has_new),
    )


def close_coverage():
    return gr.update(value="")


def confirm_add_concepts(selected: list, sid: str):
    if not sid or sid not in _sessions:
        return gr.update(choices=[], value=[]), gr.update(visible=False), "No session."
    if not selected:
        return gr.update(choices=[], value=[]), gr.update(visible=False), "No concepts selected."
    sess = _sessions[sid]
    existing = set(sess.all_concepts)
    added = [c for c in selected if c not in existing]
    sess.all_concepts.extend(added)
    sess.extra_concepts.extend(added)
    sess.file_analysis = {}
    msg = (
        f"Queued {len(added)} concept(s) for next iteration: {', '.join(added)}"
        if added else "All selected concepts already in list."
    )
    sess.log.append(f"[{_ts()}] {msg}")
    return gr.update(choices=[], value=[]), gr.update(visible=False), msg


# ── One-shot (control group) generation ─────────────────────────────────────────
# This is a single blocking LLM call, not the interactive agent's background
# thread + queue + poll loop: the control-group task in User-study.md is a
# one-shot prompt with no iteration or dialogue, so it deliberately shares none
# of the interactive tool's session/poll machinery. Once run, it locks the
# interactive tool out for that profile (both in the UI and, via the
# "used_one_shot" profile flag checked in start(), even after a page reload)
# so a between-subjects participant can't use both conditions.
def run_oneshot(prompt: str, file_obj, user_name: str):
    _NOOP = tuple(gr.update() for _ in range(8))
    prompt = (prompt or "").strip()
    user_name = (user_name or "").strip()

    if not prompt:
        return (*_NOOP, "⚠️ Enter a domain prompt first.")
    if not user_name:
        return (*_NOOP, "⚠️ Please save your profile in User Setup before starting.")

    profile = _load_user_profile(user_name)
    if not profile.get("pre_responses"):
        return (*_NOOP, "⚠️ Please complete the pre-use questionnaire in User Setup before starting the one-shot generation.")

    file_content = ""
    if file_obj:
        try:
            file_content, _ = _read_file(file_obj)
        except Exception:
            file_content = ""

    # Force the same concept vocabulary the pre/post questionnaire is
    # calibrated against, so the one-shot condition is quizzable exactly
    # like the interactive condition — unlike the interactive path this is
    # a hard requirement in the prompt, not a nudge, since there's no
    # elicitation round-trip here to steer it back on track.
    required_concepts = DOMAINS.get(profile.get("domain", ""), {}).get("concepts", [])
    generation_prompt = prompt
    if required_concepts:
        generation_prompt += (
            "\n\nThe metamodel must include exactly these core concepts, named exactly "
            "as given (do not rename, merge, split, or omit any of them): "
            + ", ".join(required_concepts) + "."
        )

    metamodel = generate_direct(generation_prompt, file_content)
    _save_user_profile(user_name, extra={"used_one_shot": True, "tool_completed": True})

    out_dir = Path("session_logs")
    out_dir.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    oneshot_record = {
        "timestamp": ts,
        "method": "one_shot",
        "user": user_name,
        "domain": profile.get("domain", ""),
        "prompt": prompt,
        "final_metamodel": metamodel,
    }
    (out_dir / f"session_{ts}_oneshot.json").write_text(json.dumps(oneshot_record, indent=2))
    log_session(oneshot_record)  # also pushed off-Space; local session_logs/ alone won't survive a Space restart

    return (
        gr.update(interactive=False),   # prompt_box: keep the prompt visible, lock editing
        gr.update(visible=False),       # start_btn: interactive tool is no longer reachable
        gr.update(visible=False),       # oneshot_btn: prevent a second run
        gr.update(interactive=False),   # file_upload
        gr.update(visible=False),       # main_workspace (chat + review panels)
        gr.update(value=_to_svg(metamodel, "One-Shot Metamodel")),
        gr.update(value=metamodel),     # final_jjscript_box: raw JjScript alongside the rendered diagram
        gr.update(value={}),
        "✅ One-shot generation complete. Please go to **User Setup** and complete the **post-use questionnaire**.",
    )


# ── CSS ────────────────────────────────────────────────────────────────────────
CSS = """
/* ── Global reset ── */
body, .gradio-container {
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    background: #f1f5f9 !important;
    color: #1e293b !important;
}
/* Blocks(fill_width=True) makes the app use the full viewport width; cap it
   so the layout doesn't stretch edge-to-edge into unreadable long lines on
   ultra-wide monitors, while still using far more space than the default
   centered ~1200px column. */
.gradio-container {
    width: 100% !important;
    max-width: 1800px !important;
    margin: 0 auto !important;
}

/* ── Group "card" backgrounds ──
   Gradio renders a gr.Group as an outer wrapper plus an inner `.styler` div
   that actually holds the content and collapses when the group is hidden.
   Card chrome (background/border/padding/shadow) must live on `.styler`,
   not on the outer wrapper class — otherwise the wrapper's own padding and
   border stay on screen as an empty "ghost card" whenever the group's
   content is toggled to visible=False (e.g. switching to the User Setup
   page), and the theme's default gray gap-fill shows through any part of
   the card with no opaque content (e.g. the <hr> divider, empty gr.HTML
   panes). ── */
.input-bar > .styler,
.results-section > .styler,
.approval-card > .styler {
    background: #ffffff;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.input-bar > .styler { border: 1px solid #e2e8f0; padding: 12px 14px 10px; }
.input-bar { margin-bottom: 10px; }
.results-section > .styler { border: 1px solid #e2e8f0; overflow: hidden; }
.results-section { margin-top: 10px; }
.approval-card > .styler {
    border: none;
    border-top: 3px solid #2563eb;
    border-radius: 0;
    padding: 16px;
    box-shadow: none;
}
.profile-page > .styler {
    border: 1px solid #e2e8f0;
    padding: 16px 18px;
}

/* ── Quiz radios (pre/post questionnaire) ──
   Gradio's default Radio layout is a wrapping horizontal row, which breaks
   full-sentence answer options into a jumbled two-column flow. Stack them
   vertically, one option per line, for readability during a timed quiz. */
.quiz-radio .wrap {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 4px !important;
}
.quiz-radio label {
    width: 100% !important;
}
.quiz-radio { margin-bottom: 14px; }

/* ── App header ── */
.app-header {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 20px;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #2563eb;
    border-radius: 10px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.app-header-icon {
    width: 38px; height: 38px;
    background: linear-gradient(135deg, #2563eb, #4f46e5);
    border-radius: 9px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(37,99,235,0.3);
}
.app-header-title {
    font-size: 18px;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.3px;
    margin: 0 0 1px;
}
.app-header-sub {
    font-size: 12.5px;
    color: #64748b;
    margin: 0;
}

/* ── Shrink the Gradio file upload to a compact strip ── */
.file-row .upload-container,
.file-row .file-preview,
.file-row .wrap {
    min-height: 44px !important;
    max-height: 52px !important;
    padding: 0 !important;
}
.file-row .upload-container .icon-wrap { display: none !important; }
.file-row .upload-container p { font-size: 12px !important; margin: 0 !important; line-height: 44px !important; }
.file-row .upload-container .or { display: none !important; }

/* ── User status column (next to the file upload) ── */
.user-status-col {
    justify-content: center;
    gap: 2px !important;
}
.user-status-col p { margin: 0 !important; font-size: 13px; }

/* ── Buttons ──
   Alignment lives on the row (align-items), not on each button
   individually — a per-button `align-self` only fixes that one button,
   so any sibling without the same override (as User Setup used to be)
   drifts out of line the moment row heights aren't pixel-identical
   (e.g. one label wrapping at a narrower viewport). All three buttons
   also share the same height/padding/font metrics so their boxes are
   identical regardless of label length. ── */
.prompt-row { align-items: flex-end; }

#start-btn, #oneshot-btn, #profile-nav-btn {
    min-height: 40px !important;
    max-height: 44px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 0 18px !important;
    border-radius: 8px !important;
    white-space: nowrap !important;
    transition: opacity .15s !important;
}

#start-btn {
    background: linear-gradient(135deg, #2563eb, #4f46e5) !important;
    border: none !important;
    box-shadow: 0 2px 6px rgba(37,99,235,0.35) !important;
}
#start-btn:hover { opacity: .88 !important; }

#oneshot-btn {
    background: #fff7ed !important;
    color: #9a3412 !important;
    border: 1px solid #fdba74 !important;
}
#oneshot-btn:hover { opacity: .82 !important; }

#cov-btn {
    min-height: 36px !important;
    max-height: 40px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    padding: 0 14px !important;
    align-self: center !important;
    border-radius: 8px !important;
    white-space: nowrap !important;
}

/* ── File status ── */
.file-status,
.file-row .form {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
.file-status input,
.file-status textarea {
    font-size: 12px !important;
    color: #059669 !important;
    background: transparent !important;
    border: none !important;
    padding: 2px 0 0 !important;
    font-weight: 500 !important;
}

/* ── Divider ── */
.input-divider {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 8px 0;
}

/* ── Main panels ── */
.chat-panel, .review-panel {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

/* ── Chatbot ── */
.gradio-chatbot {
    border: none !important;
    border-radius: 0 !important;
    background: #ffffff !important;
}

/* ── Review workspace placeholder ── */
.ws-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 260px;
    padding: 32px;
    color: #94a3b8;
    text-align: center;
}
.ws-placeholder-icon {
    width: 48px; height: 48px;
    background: #f1f5f9;
    border: 1.5px dashed #cbd5e1;
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 12px;
}
.ws-placeholder-title { font-size: 13px; font-weight: 600; color: #64748b; margin: 0 0 4px; }
.ws-placeholder-sub { font-size: 12px; color: #94a3b8; margin: 0; }

/* ── Answer input row ── */
#answer-box input,
#answer-box textarea {
    border-radius: 8px !important;
    font-size: 13.5px !important;
    border: 1.5px solid #e2e8f0 !important;
    transition: border-color .15s !important;
}
#answer-box input:focus,
#answer-box textarea:focus { border-color: #2563eb !important; }

/* ── Yes/No and challenge buttons ── */
.yn-btn, .ch-btn {
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    min-height: 38px !important;
}

/* ── Approval card ── */
.explanation-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 13.5px;
    color: #334155;
}
.explanation-box p { margin: 0; }
.approval-card .concept-title {
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 12px;
}

/* ── Approve / Reject ── */
.approve-btn {
    background: #16a34a !important;
    border-color: #16a34a !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    box-shadow: 0 2px 5px rgba(22,163,74,.25) !important;
}
.reject-btn {
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
}

.reject-feedback-btn {
    background: #ea580c !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    color: white !important;
}

.svg-preview {
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    overflow: hidden;
    margin-bottom: 12px;
    background: #ffffff;
    box-shadow: 0 1px 5px rgba(15,23,42,0.08);
}
.svg-preview.current-chunk {
    border-color: #fb923c;
    box-shadow: 0 0 0 3px rgba(251,146,60,0.18);
}
.svg-preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    font-size: 13px;
    color: #334155;
}
.svg-preview-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}
.svg-preview-actions a {
    color: #2563eb;
    text-decoration: none;
    font-weight: 600;
}
.svg-preview-inner {
    max-height: 440px;
    overflow: auto;
    padding: 10px;
    background: #ffffff;
}
.svg-preview-inner svg {
    width: 100%;
    height: auto;
    display: block;
}
.svg-overlay {
    position: fixed;
    inset: 0;
    visibility: hidden;
    opacity: 0;
    transition: opacity 0.18s ease;
    background: rgba(15,23,42,0.86);
    z-index: 12000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
}
.svg-overlay:target {
    visibility: visible;
    opacity: 1;
}
.svg-overlay-content {
    position: relative;
    width: min(100%, 1200px);
    max-height: 100%;
    overflow: auto;
    background: #0f172a;
    border-radius: 18px;
    padding: 20px;
}
.svg-overlay-title {
    color: #f8fafc;
    font-size: 17px;
    font-weight: 700;
    margin-bottom: 8px;
}
.svg-overlay-hint {
    color: #cbd5e1;
    font-size: 13px;
    margin-bottom: 14px;
}
.svg-overlay-inner {
    overflow: auto;
    max-height: calc(100vh - 140px);
}
.svg-overlay-inner svg {
    width: 100%;
    height: auto;
}
.svg-overlay-close {
    position: absolute;
    top: 14px;
    right: 14px;
    color: #f8fafc;
    font-size: 24px;
    text-decoration: none;
}


/* ── Answer col padding ── */
.answer-col { padding: 8px 12px 12px !important; }

/* ── Log ── */
.log-textarea textarea {
    font-family: "JetBrains Mono", "SF Mono", "Fira Code", monospace !important;
    font-size: 11.5px !important;
    color: #475569 !important;
    background: #f8fafc !important;
    line-height: 1.6 !important;
}

/* ── Section labels ── */
.section-label {
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .07em;
    color: #94a3b8;
    padding: 10px 14px 0;
}
"""

# ── Layout ─────────────────────────────────────────────────────────────────────
with gr.Blocks(title="Metamodel Generator", fill_width=True) as demo:
    sid_state = gr.State("")
    user_name_state = gr.State("")
    domain_state = gr.State("")

    # ── Header ────────────────────────────────────────────────────────────────
    main_header = gr.HTML("""
    <div class="app-header">
      <div class="app-header-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2"
             stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="7" height="7" rx="1"/>
          <rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="14" y="14" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/>
        </svg>
      </div>
      <div>
        <div class="app-header-title">Metamodel Generator</div>
        <div class="app-header-sub">Describe your software domain — get a JjScript metamodel built concept-by-concept through guided elicitation.</div>
      </div>
    </div>
    """)

    # ── Input bar ─────────────────────────────────────────────────────────────
    # NOTE: the visibility toggle (User Setup <-> tool) is applied to the outer
    # `gr.Column`, not the inner `gr.Group`. Gradio's Group component does not
    # add a "hide" class to its own wrapper when `visible=False` — only to the
    # Rows/Forms nested inside it — so a Group carrying its own border/padding
    # CSS is left behind as an empty "ghost card" when hidden. A plain Column
    # hides itself correctly, so it owns the toggle while the Group underneath
    # (never independently toggled) keeps the seamless card styling.
    with gr.Column() as input_bar:
        with gr.Group(elem_classes="input-bar"):
            # Row 1: prompt + start + profile nav
            gr.HTML('<div class="section-label" style="padding:0 0 6px">Domain prompt</div>')
            with gr.Row(equal_height=True, elem_classes="prompt-row"):
                prompt_box = gr.Textbox(
                    placeholder="e.g. A university course management system",
                    show_label=False,
                    scale=6, lines=1,
                )
                start_btn = gr.Button("▶ Start", variant="primary", scale=1,
                                      min_width=100, elem_id="start-btn", size="sm")
                oneshot_btn = gr.Button("⚡ One-Shot Generation", variant="secondary", scale=1,
                                        min_width=170, elem_id="oneshot-btn", size="sm")
                profile_nav_btn = gr.Button("👤 User Setup", variant="secondary", scale=1,
                                            min_width=130, elem_id="profile-nav-btn", size="sm")

            gr.HTML('<hr class="input-divider">', visible=False)

            # Row 2: compact file upload + coverage button + status.
            # The file-upload widget is hidden from the layout (not requested
            # for the study) — its wiring (attach_file, coverage analysis,
            # run_oneshot's file_obj) is left intact and just never receives
            # a file, so nothing downstream had to change.
            gr.HTML('<div class="section-label" style="padding:0 0 6px">Attach file for coverage analysis (PDF / TXT / MD)</div>', visible=False)
            with gr.Row(equal_height=True, elem_classes="file-row"):
                with gr.Column(visible=False):
                    file_upload = gr.File(
                        show_label=False,
                        file_types=[".pdf", ".txt", ".md"],
                        scale=6,
                        height=52,
                    )
                    open_cov_btn = gr.Button(
                        "Coverage Report",
                        variant="secondary", visible=False,
                        elem_id="cov-btn", size="sm",
                    )
                    file_status_lbl = gr.Textbox(
                        value="", interactive=False, show_label=False, lines=1,
                        placeholder="No file attached", container=False,
                        max_lines=1, elem_classes="file-status",
                    )

                with gr.Column(scale=2, min_width=160, elem_classes="user-status-col"):
                    current_user_label = gr.Markdown("**Current participant:** None")
                    user_warning = gr.Markdown("", elem_id="user-warning")

    # ── Main workspace ────────────────────────────────────────────────────────
    with gr.Row(equal_height=False) as main_workspace:

        # LEFT — conversation
        with gr.Column(scale=5, elem_classes="chat-panel"):
            gr.HTML('<div class="section-label">Conversation</div>')
            chatbot = gr.Chatbot(
                label="",
                height=460,
                show_label=False,
                placeholder="Enter a domain prompt above and click ▶ Start",
                elem_classes="gradio-chatbot",
            )

            with gr.Column(elem_classes="answer-col"):
                with gr.Row(visible=False) as answer_row:
                    answer_box = gr.Textbox(
                        placeholder="Type your answer…",
                        label="", scale=5, lines=1,
                        show_label=False, container=False,
                        elem_id="answer-box",
                    )
                    submit_btn = gr.Button("Send ↵", variant="primary", scale=1,
                                          min_width=70, size="sm")

                with gr.Row(visible=False) as yes_no_row:
                    yes_btn = gr.Button("✓ Yes", variant="primary",   scale=1,
                                        size="sm", elem_classes="yn-btn")
                    no_btn  = gr.Button("✗ No",  variant="secondary", scale=1,
                                        size="sm", elem_classes="yn-btn")

                with gr.Row(visible=False) as challenge_row:
                    gr.Markdown("**Challenge level:**", elem_classes="section-label")
                    ch_easy_btn = gr.Button("Easy",     variant="secondary", scale=1,
                                            size="sm", elem_classes="ch-btn")
                    ch_mod_btn  = gr.Button("Moderate", variant="primary",   scale=1,
                                            size="sm", elem_classes="ch-btn")
                    ch_hard_btn = gr.Button("Hard",     variant="stop",      scale=1,
                                            size="sm", elem_classes="ch-btn")

        # RIGHT — review workspace
        with gr.Column(scale=7, elem_classes="review-panel"):
            gr.HTML('<div class="section-label">Review Workspace</div>')

            gr.HTML("""
            <div class="ws-placeholder">
              <div class="ws-placeholder-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#94a3b8"
                     stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                  <line x1="16" y1="13" x2="8" y2="13"/>
                  <line x1="16" y1="17" x2="8" y2="17"/>
                  <polyline points="10 9 9 9 8 9"/>
                </svg>
              </div>
              <div class="ws-placeholder-title">Waiting for concepts</div>
              <div class="ws-placeholder-sub">Metamodel chunks will appear here for approval once the agent proposes them.</div>
            </div>
            """)

            with gr.Column(visible=False) as approval_panel:
                with gr.Group(elem_classes="approval-card"):
                    concept_lbl = gr.Markdown("**Concept**")
                    gr.HTML('<hr style="border:none;border-top:1px solid #e2e8f0;margin:8px 0 14px">')

                    with gr.Row(equal_height=True):
                        with gr.Column():
                            gr.Markdown("##### Metamodel chunk")
                            chunk_box = gr.HTML()
                            with gr.Accordion("📄 Raw JjScript", open=False):
                                chunk_text_box = gr.Code(
                                    value="", language=None, interactive=False,
                                    show_label=False, lines=12,
                                )
                        with gr.Column():
                            gr.Markdown("##### Sample instance")
                            sample_box = gr.HTML()
                            gr.Markdown("##### Explanation")
                            explanation_box = gr.Markdown(value="", elem_classes="explanation-box")

                    with gr.Accordion("Auto-validation details", open=False):
                        validation_box = gr.JSON(show_label=False)

                    gr.HTML('<hr style="border:none;border-top:1px solid #e2e8f0;margin:14px 0 10px">')

                    with gr.Row():
                        approve_btn = gr.Button("✓ Approve", variant="primary", scale=1,
                                                elem_classes="approve-btn")
                        reject_btn  = gr.Button("✗ Reject",  variant="stop",    scale=1,
                                                elem_classes="reject-btn")

                    with gr.Group(visible=False, elem_id="reject-feedback-group") as reject_feedback_group:
                        gr.Markdown("**What did you not like about this chunk? This feedback will help the model improve the next iteration.**")
                        reject_reason_box = gr.Textbox(
                            placeholder="Describe the problem so the model can improve this chunk...",
                            lines=3, show_label=False, scale=4,
                        )
                        submit_rejection_feedback_btn = gr.Button(
                            "Submit rejection feedback",
                            variant="stop", scale=1, elem_classes="reject-feedback-btn"
                        )

    # ── Results (tabbed) ──────────────────────────────────────────────────────
    with gr.Column() as results_section:
        with gr.Group(elem_classes="results-section"):
            with gr.Tabs():
                with gr.TabItem("📐 Final Metamodel"):
                    with gr.Row():
                        with gr.Column(scale=7):
                            output_box = gr.HTML(label="Final metamodel")
                            with gr.Accordion("📄 Raw JjScript", open=False):
                                final_jjscript_box = gr.Code(
                                    value="", language=None, interactive=False,
                                    show_label=False, lines=12,
                                )
                        with gr.Column(scale=3):
                            final_validation_box = gr.JSON(label="Validation report", open=False)

                with gr.TabItem("📋 Activity Log"):
                    log_box = gr.Textbox(
                        label="", lines=14, max_lines=16, interactive=False,
                        elem_classes="log-textarea",
                        placeholder="Session log will appear here once started…",
                    )

    # ── Hidden / overlay elements ─────────────────────────────────────────────
    coverage_popup_html = gr.HTML(value="", elem_id="coverage-popup-host")

    with gr.Group(visible=False) as new_concepts_group:
        gr.HTML('<hr style="border:none;border-top:1px solid #e2e8f0;margin:10px 0">')
        gr.Markdown("**New domain concepts found — select which to add to the next iteration:**")
        new_concepts_box = gr.CheckboxGroup(choices=[], label="", interactive=True)
        confirm_add_btn  = gr.Button("Queue selected for next iteration",
                                     variant="primary", scale=0, size="sm")

    timer = gr.Timer(value=1.0)

    with gr.Column(visible=False) as profile_page:
        with gr.Group(elem_classes="profile-page"):
            gr.HTML("""
            <div class="app-header">
              <div class="app-header-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2"
                     stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="3" width="7" height="7" rx="1"/>
                  <rect x="14" y="3" width="7" height="7" rx="1"/>
                  <rect x="14" y="14" width="7" height="7" rx="1"/>
                  <rect x="3" y="14" width="7" height="7" rx="1"/>
                </svg>
              </div>
              <div>
                <div class="app-header-title">User Setup</div>
                <div class="app-header-sub">Enter your participant ID first, then complete the pre-use questionnaire. Fill the post-use questionnaire after using the tool.</div>
              </div>
            </div>
            """)

            gr.Markdown(
                "**This study is anonymous — do not enter your name.** Use a participant "
                "ID instead — a number or a short code (your researcher will give you one, "
                "or pick any one you like) — and save it before using the tool. Your "
                "responses are persisted to `user_profiles/` as JSON, identified only by "
                "that ID.\n\n"
                "All data is collected anonymously, with digital informed consent obtained "
                "from each participant before the study begins. **You can stop "
                "participating in this experiment at any time, for any reason, without any "
                "consequences to you.**"
            )

            username_box = gr.Textbox(
                label="Participant ID (number or code)",
                placeholder="e.g. 07 or P07",
                scale=4, lines=1,
            )

            domain_radio = gr.Radio(
                choices=[(v["label"], k) for k, v in DOMAINS.items()],
                label="Study domain (assigned by the researcher)",
                elem_classes="quiz-radio",
            )

            consent_checkbox = gr.Checkbox(
                label="I have read the information above and I consent to take part in this study.",
                value=False,
            )

            with gr.Row(equal_height=True):
                save_name_btn = gr.Button("Save name", variant="primary", scale=1, min_width=130, size="sm")
                back_to_tool_btn = gr.Button("← Back to tool", variant="secondary", scale=1, min_width=130, size="sm")

            profile_status = gr.Markdown("Your profile is not saved yet.")

            # Two domains, each with its own pre/post question bank (see
            # app_modules/quiz.py). Only the group matching the saved profile's
            # domain is ever made visible — the other stays hidden throughout.
            bp_pre_checks = []
            with gr.Group(visible=False) as bp_pre_form_group:
                gr.Markdown(f"### Pre-use questionnaire — {DOMAINS['bp']['label']}")
                for question in DOMAINS["bp"]["pre"]:
                    gr.Markdown(f"**{question['id'].upper()}** {question['text']}")
                    bp_pre_checks.append(
                        gr.CheckboxGroup(
                            choices=question["options"],
                            label="Choose one or more",
                            type="value",
                            elem_classes="quiz-radio",
                        )
                    )
                bp_submit_pre_btn = gr.Button("Submit pre-use evaluation", variant="primary", scale=1)

            engine_pre_checks = []
            with gr.Group(visible=False) as engine_pre_form_group:
                gr.Markdown(f"### Pre-use questionnaire — {DOMAINS['engine']['label']}")
                for question in DOMAINS["engine"]["pre"]:
                    gr.Markdown(f"**{question['id'].upper()}** {question['text']}")
                    engine_pre_checks.append(
                        gr.CheckboxGroup(
                            choices=question["options"],
                            label="Choose one or more",
                            type="value",
                            elem_classes="quiz-radio",
                        )
                    )
                engine_submit_pre_btn = gr.Button("Submit pre-use evaluation", variant="primary", scale=1)

            pre_form_status = gr.Markdown("")

            bp_post_checks = []
            with gr.Group(visible=False) as bp_post_form_group:
                gr.Markdown(f"### Post-use questionnaire — {DOMAINS['bp']['label']}")
                for question in DOMAINS["bp"]["post"]:
                    gr.Markdown(f"**{question['id'].upper()}** {question['text']}")
                    bp_post_checks.append(
                        gr.CheckboxGroup(
                            choices=question["options"],
                            label="Choose one or more",
                            type="value",
                            elem_classes="quiz-radio",
                        )
                    )
                bp_submit_post_btn = gr.Button("Submit post-use evaluation", variant="primary", scale=1)

            engine_post_checks = []
            with gr.Group(visible=False) as engine_post_form_group:
                gr.Markdown(f"### Post-use questionnaire — {DOMAINS['engine']['label']}")
                for question in DOMAINS["engine"]["post"]:
                    gr.Markdown(f"**{question['id'].upper()}** {question['text']}")
                    engine_post_checks.append(
                        gr.CheckboxGroup(
                            choices=question["options"],
                            label="Choose one or more",
                            type="value",
                            elem_classes="quiz-radio",
                        )
                    )
                engine_submit_post_btn = gr.Button("Submit post-use evaluation", variant="primary", scale=1)

            post_form_status = gr.Markdown("")

    # ── Output lists ──────────────────────────────────────────────────────────
    START_OUTPUTS = [
        sid_state, chatbot, answer_box,
        answer_row, yes_no_row, challenge_row, approval_panel,
        output_box, final_validation_box, log_box, user_warning,
    ]

    POLL_OUTPUTS = [
        chatbot,
        answer_row, yes_no_row, challenge_row, approval_panel,
        concept_lbl, chunk_box, chunk_text_box, sample_box, explanation_box, validation_box,
        output_box, final_jjscript_box, final_validation_box, log_box,
    ]

    # ── Wiring (ALL UNCHANGED) ─────────────────────────────────────────────────
    start_btn.click(start, [prompt_box, sid_state, user_name_state], START_OUTPUTS)
    oneshot_btn.click(
        run_oneshot,
        [prompt_box, file_upload, user_name_state],
        [prompt_box, start_btn, oneshot_btn, file_upload, main_workspace,
         output_box, final_jjscript_box, final_validation_box, user_warning],
    )
    timer.tick(poll, [sid_state], POLL_OUTPUTS)

    submit_btn.click(submit_answer, [answer_box, sid_state], [answer_box, answer_row, yes_no_row])
    answer_box.submit(submit_answer, [answer_box, sid_state], [answer_box, answer_row, yes_no_row])

    yes_btn.click(submit_yes_no, [gr.State("yes"), sid_state], [answer_row, yes_no_row])
    no_btn.click( submit_yes_no, [gr.State("no"),  sid_state], [answer_row, yes_no_row])

    ch_easy_btn.click(submit_challenge_level, [gr.State("easy"),     sid_state], [answer_row, yes_no_row, challenge_row])
    ch_mod_btn.click( submit_challenge_level, [gr.State("moderate"), sid_state], [answer_row, yes_no_row, challenge_row])
    ch_hard_btn.click(submit_challenge_level, [gr.State("hard"),     sid_state], [answer_row, yes_no_row, challenge_row])

    file_upload.change(attach_file, [file_upload, sid_state], [file_status_lbl, open_cov_btn])
    open_cov_btn.click(open_coverage, [sid_state],
                       [coverage_popup_html, new_concepts_box, new_concepts_group])
    confirm_add_btn.click(confirm_add_concepts, [new_concepts_box, sid_state],
                          [new_concepts_box, new_concepts_group, file_status_lbl])

    approve_btn.click(approve, [sid_state], [approval_panel, reject_feedback_group])
    reject_btn.click(begin_reject_feedback, [sid_state], [reject_feedback_group, approve_btn, reject_btn, reject_reason_box])
    submit_rejection_feedback_btn.click(
        submit_rejection_feedback,
        [reject_reason_box, sid_state],
        [reject_feedback_group, approve_btn, reject_btn, reject_reason_box],
    )

    profile_nav_btn.click(_show_profile_page, [user_name_state],
                          [main_header, input_bar, main_workspace, results_section, profile_page,
                           bp_pre_form_group, engine_pre_form_group,
                           bp_post_form_group, engine_post_form_group])
    back_to_tool_btn.click(_show_tool_page, [domain_state],
                          [main_header, input_bar, main_workspace, results_section, profile_page, prompt_box])
    save_name_btn.click(_save_user_name,
                        [username_box, domain_radio, consent_checkbox],
                        [current_user_label, profile_status, user_name_state, domain_state,
                         bp_pre_form_group, engine_pre_form_group, bp_post_form_group, engine_post_form_group])
    bp_submit_pre_btn.click(_submit_bp_pre_evaluation,
                            [username_box, *bp_pre_checks],
                            [pre_form_status, profile_status, bp_post_form_group])
    engine_submit_pre_btn.click(_submit_engine_pre_evaluation,
                                [username_box, *engine_pre_checks],
                                [pre_form_status, profile_status, engine_post_form_group])
    bp_submit_post_btn.click(_submit_bp_post_evaluation,
                             [username_box, *bp_post_checks],
                             [post_form_status, profile_status])
    engine_submit_post_btn.click(_submit_engine_post_evaluation,
                                 [username_box, *engine_post_checks],
                                 [post_form_status, profile_status])


FONT_HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
"""

if __name__ == "__main__":
    share = "--share" in sys.argv
    demo.launch(server_name="0.0.0.0", server_port=7860, share=share,
               theme=gr.themes.Soft(), css=CSS, head=FONT_HEAD)