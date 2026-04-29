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


# ── Color palette ──────────────────────────────────────────────────────────────
_COLORS = [
    "#FFD700","#90EE90","#87CEEB","#FFB6C1","#DDA0DD",
    "#F0E68C","#98FB98","#ADD8E6","#FFA07A","#20B2AA",
    "#FF8C00","#9370DB","#3CB371","#DC143C","#00CED1",
]


def _to_svg(jjscript: str, title: str = "Graph") -> str:
    text = jjscript.strip()
    for fence in ("```jjscript", "```python", "```"):
        text = text.replace(fence, "")
    text = text.strip()
    if not text:
        return ""
    try:
        classes, instances = parse_jjscript(text)
        return build_svg(classes, instances, title=title)
    except Exception:
        return f"<pre style='white-space:pre-wrap'>{html.escape(text)}</pre>"


def _read_file(file_obj) -> tuple[str, str]:
    """Extract text content from a file object. Returns (content, filename)."""
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
        self.extra_concepts: list[str] = []   # queued by user for next agent round
        self.current_metamodel: str = ""      # latest known metamodel JJScript


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


# ── Coverage analysis ──────────────────────────────────────────────────────────
def _run_coverage_analysis(file_content: str, concepts: list[str], metamodel: str) -> dict:
    client = LLMClient()

    # Deterministically find which concepts are already modeled in the JJScript
    modeled = re.findall(
        r"create\s+(?:abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)", metamodel, re.IGNORECASE
    )
    modeled_lower = {m.lower() for m in modeled}
    modeled_str = ", ".join(modeled) if modeled else "(none yet)"

    # Concepts approved/proposed but not yet generated in the metamodel
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
        "  coverage_percentage: integer 0-100 (how much of the doc is covered by modeled concepts)\n"
    )

    result = client.invoke_json(prompt)
    result["not_yet_modeled"] = not_yet_modeled
    result["modeled_concepts"] = modeled
    return result


def _build_coverage_html(file_content: str, analysis: dict, all_concepts: list[str]) -> str:
    not_yet_modeled = analysis.get("not_yet_modeled", [])
    new_concepts    = analysis.get("new_concepts", [])
    coverage_pct    = analysis.get("coverage_percentage", 0)
    modeled         = analysis.get("modeled_concepts", [])
    sentence_highlights = analysis.get("sentence_highlights", [])

    # Build highlight spans: whitespace-normalised regex match against raw text
    spans: list[tuple[int, int, str]] = []
    for item in sentence_highlights:
        sentence = item.get("sentence", "").strip()
        concept  = item.get("concept", "")
        if not sentence:
            continue
        pattern = r"\s+".join(re.escape(w) for w in sentence.split())
        m = re.search(pattern, file_content, re.IGNORECASE)
        if m:
            spans.append((m.start(), m.end(), concept))

    spans.sort(key=lambda x: x[0])
    merged: list[tuple[int, int, str]] = []
    for span in spans:
        if merged and span[0] < merged[-1][1]:
            continue
        merged.append(span)

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

    # Modeled chips (green)
    modeled_chips = "".join(
        f'<span style="display:inline-block;background:#dcfce7;color:#15803d;border:1px solid #86efac;'
        f'border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;margin:3px 3px 3px 0">'
        f'&#10003; {html.escape(c)}</span>'
        for c in modeled
    ) if modeled else '<span style="color:#9ca3af;font-size:13px">None modeled yet</span>'

    # Not yet modeled chips (amber)
    pending_chips = "".join(
        f'<span style="display:inline-block;background:#fef9c3;color:#92400e;border:1px solid #fcd34d;'
        f'border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;margin:3px 3px 3px 0">'
        f'&#9679; {html.escape(c)}</span>'
        for c in not_yet_modeled
    ) if not_yet_modeled else '<span style="color:#9ca3af;font-size:13px">All concepts modeled</span>'

    # New concepts chips (blue)
    new_chips = "".join(
        f'<span style="display:inline-block;background:#dbeafe;color:#1e40af;border:1px solid #93c5fd;'
        f'border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;margin:3px 3px 3px 0">'
        f'+ {html.escape(c)}</span>'
        for c in new_concepts
    ) if new_concepts else '<span style="color:#9ca3af;font-size:13px">None discovered</span>'

    return f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1f2937">

  <!-- Header bar -->
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

  <!-- Concept status cards -->
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:18px">

    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:14px">
      <div style="font-size:11px;font-weight:700;color:#15803d;text-transform:uppercase;
                  letter-spacing:.07em;margin-bottom:10px">&#10003; Modeled so far</div>
      <div>{modeled_chips}</div>
    </div>

    <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:14px">
      <div style="font-size:11px;font-weight:700;color:#92400e;text-transform:uppercase;
                  letter-spacing:.07em;margin-bottom:10px">&#9679; Pending modeling</div>
      <div>{pending_chips}</div>
    </div>

    <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:14px">
      <div style="font-size:11px;font-weight:700;color:#1e40af;text-transform:uppercase;
                  letter-spacing:.07em;margin-bottom:10px">+ New in document</div>
      <div>{new_chips}</div>
    </div>

  </div>

  <!-- Document with highlights -->
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
        if context.get("validation_stage") == "challenge_selection":
            sess.chat.append({"role": "assistant", "content": question})
            sess.waiting_elicitation = True
            sess.current_elicitation_question = question
            sess.elicit_q.put(question)
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

    def human_validator(payload: dict) -> bool:
        sess.log.append(f"[{_ts()}] Review: {payload.get('concept', '')}")
        sess.pending_payload = payload
        if payload.get("chunk"):
            sess.current_metamodel = payload["chunk"]
            sess.file_analysis = {}  # invalidate so next open re-runs with latest metamodel
        sess.waiting_approval = True
        sess.approval_q.put(payload)
        decision = sess.approval_a.get(block=True)
        sess.waiting_approval = False
        sess.log.append(f"[{_ts()}] {'OK' if decision else 'X'} {payload.get('concept', '')}")
        return decision

    try:
        initial_state = (
            {"attached_file_content": sess.attached_file_content}
            if sess.attached_file_content else {}
        )
        result = agent.run_iterative(
            prompt,
            human_validator=human_validator,
            user_responder=user_responder,
            initial_state=initial_state,
        )
        sess.log.append(f"[{_ts()}] Done.")

        # Process any extra concepts the user queued during the run
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
        "log": sess.log,
        "concepts": result.get("concepts", []),
        "final_metamodel": result.get("final_metamodel", ""),
        "final_sample_model": result.get("cumulative_sample_model", ""),
        "final_validation": result.get("final_validation", {}),
    }
    (out_dir / f"session_{ts}.json").write_text(json.dumps(data, indent=2))


# ── Event handlers ─────────────────────────────────────────────────────────────
def start(prompt: str, sid: str):
    # START_OUTPUTS (10): sid, chatbot, answer_box, answer_row, yes_no_row,
    #                     challenge_row, approval_panel, output_box, final_validation_box, log_box
    _EMPTY = (sid, [], "", gr.update(visible=False), gr.update(visible=False),
              gr.update(visible=False), gr.update(visible=False),
              gr.update(), gr.update(), "Enter a prompt first.")
    if not prompt.strip():
        return _EMPTY

    new_sid = str(uuid.uuid4())
    sess = _Session()
    sess.log.append(f"[{_ts()}] Started: {prompt[:80]}")
    sess.chat.append({
        "role": "assistant",
        "content": (
            f"Starting metamodel for: **{prompt}**\n\n"
            "I will ask a few questions to understand the domain."
        ),
    })
    _sessions[new_sid] = sess
    threading.Thread(target=_run_agent, args=(sess, prompt), daemon=True).start()

    return (new_sid, list(sess.chat), "",
            gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            gr.update(), gr.update(), f"[{_ts()}] Running...")


def poll(sid: str):
    # POLL_OUTPUTS (12): chatbot, answer_row, yes_no_row, challenge_row, approval_panel,
    #                    concept_lbl, chunk_box, sample_box, validation_box,
    #                    output_box, final_validation_box, log_box
    _noop = tuple(gr.update() for _ in range(12))
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
            gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(value=_to_svg(sess.final_result.get("final_metamodel", ""), "Final Metamodel")),
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
            gr.update(value=_to_svg(p.get("chunk", ""), f"Chunk: {p.get('concept', '')}")),
            gr.update(value=_to_svg(p.get("sample_model", ""), "Sample")),
            gr.update(value=p.get("validation", {})),
            gr.update(), gr.update(),
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
        gr.update(), gr.update(), gr.update(), gr.update(),
        gr.update(), gr.update(),
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
        _sessions[sid].approval_a.put(True)
    return gr.update(visible=False)


def reject(sid: str):
    if sid in _sessions:
        _sessions[sid].approval_a.put(False)
    return gr.update(visible=False)


def attach_file(file_obj, sid: str):
    """Read file, extract text, store in session. Returns (status_text, open_btn_update)."""
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
    sess.file_analysis = {}  # reset any previous analysis
    sess.log.append(f"[{_ts()}] File attached: {file_name} ({len(content)} chars)")
    return f"Ready: {file_name}", gr.update(visible=True)

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
    """Queue user-selected new concepts for the next agent round."""
    if not sid or sid not in _sessions:
        return gr.update(choices=[], value=[]), gr.update(visible=False), "No session."
    if not selected:
        return gr.update(choices=[], value=[]), gr.update(visible=False), "No concepts selected."
    sess = _sessions[sid]
    existing = set(sess.all_concepts)
    added = [c for c in selected if c not in existing]
    sess.all_concepts.extend(added)
    sess.extra_concepts.extend(added)   # picked up by agent after current run finishes
    sess.file_analysis = {}              # invalidate cache
    msg = (
        f"Queued {len(added)} concept(s) for next iteration: {', '.join(added)}"
        if added else "All selected concepts already in list."
    )
    sess.log.append(f"[{_ts()}] {msg}")
    return gr.update(choices=[], value=[]), gr.update(visible=False), msg


# ── CSS ────────────────────────────────────────────────────────────────────────
CSS = """
/* Coverage popup: full-screen overlay.
   NOTE: do NOT set display here — Gradio toggles display:none to hide the group.
   Position/inset/z-index apply only when Gradio makes it visible. */
#coverage-popup {
    position: fixed !important;
    inset: 0 !important;
    z-index: 10000 !important;
    background: rgba(0,0,0,0.65) !important;
    overflow-y: auto !important;
    padding: 40px 16px !important;
    box-sizing: border-box !important;
}
/* Centre the card inside the overlay */
#coverage-popup > .gr-group,
#coverage-popup > div > .gr-group,
#coverage-popup > div {
    max-width: 960px !important;
    margin: 0 auto !important;
    background: white !important;
    border-radius: 12px !important;
    padding: 24px !important;
}
/* Approval card styling */
.approval-card {
    border: 1px solid #dde2e8 !important;
    border-radius: 12px !important;
    padding: 20px !important;
    background: #fafbfc !important;
}
/* Keep footer visible so dark/light toggle remains accessible */
"""

# ── Layout ─────────────────────────────────────────────────────────────────────
with gr.Blocks(title="Metamodel Generator") as demo:
    sid_state = gr.State("")

    gr.Markdown(
        "# Metamodel Generator\n"
        "Describe your software domain — get a JjScript metamodel built concept-by-concept."
    )

    # Prompt bar
    with gr.Row():
        prompt_box = gr.Textbox(
            placeholder="e.g. A university course management system",
            label="Domain", scale=7, lines=1,
        )
        start_btn = gr.Button("Start", variant="primary", scale=1, min_width=110)

    # Two-column main area
    with gr.Row(equal_height=False):

        # LEFT — conversation
        with gr.Column(scale=4):
            chatbot = gr.Chatbot(
                label="", height=460,
                show_label=False,
                placeholder="Enter a domain above and click Start",
            )
            with gr.Row(visible=False) as answer_row:
                answer_box = gr.Textbox(
                    placeholder="Type your answer and press Enter...",
                    label="", scale=5, lines=1, show_label=False,
                )
                submit_btn = gr.Button("Send", variant="primary", scale=1, min_width=70)

            with gr.Row(visible=False) as yes_no_row:
                yes_btn = gr.Button("Yes", variant="primary",   scale=1)
                no_btn  = gr.Button("No",  variant="secondary", scale=1)

            with gr.Row(visible=False) as challenge_row:
                gr.Markdown("**Challenge level:**")
                ch_easy_btn = gr.Button("Easy",     variant="secondary", scale=1)
                ch_mod_btn  = gr.Button("Moderate", variant="primary",   scale=1)
                ch_hard_btn = gr.Button("Hard",     variant="stop",      scale=1)

        # RIGHT — approval panel (hidden until chunk is ready)
        with gr.Column(scale=6):
            with gr.Group(visible=False, elem_classes="approval-card") as approval_panel:

                concept_lbl = gr.Markdown("**Concept**")

                with gr.Row(equal_height=True):
                    with gr.Column():
                        gr.Markdown("**Metamodel chunk**")
                        chunk_box = gr.HTML()
                    with gr.Column():
                        gr.Markdown("**Sample instance**")
                        sample_box = gr.HTML()

                with gr.Accordion("Auto-validation details", open=False):
                    validation_box = gr.JSON(show_label=False)

                gr.HTML('<hr style="margin:14px 0;border:none;border-top:1px solid #e0e0e0">')

                with gr.Row():
                    approve_btn = gr.Button("Approve", variant="primary", scale=1)
                    reject_btn  = gr.Button("Reject",  variant="stop",    scale=1)

    # Persistent file attachment + coverage — always visible after file is attached
    with gr.Row():
        with gr.Column(scale=8):
            with gr.Row(equal_height=True):
                file_upload = gr.File(
                    label="Attach PDF or text for coverage analysis",
                    file_types=[".pdf", ".txt", ".md"],
                    scale=4,
                )
                open_cov_btn = gr.Button(
                    "Open Coverage Report",
                    variant="secondary", scale=1, min_width=200,
                    visible=False,
                )
            file_status_lbl = gr.Textbox(
                value="", interactive=False, show_label=False, lines=1,
                placeholder="Attach a file to analyse coverage at any point...",
                max_lines=1,
            )
        with gr.Column(scale=4):
            pass  # reserved for balance

    # Bottom — final result + log
    with gr.Row():
        with gr.Column(scale=5):
            output_box = gr.HTML(label="Final metamodel")
        with gr.Column(scale=3):
            final_validation_box = gr.JSON(label="Final validation", open=False)
        with gr.Column(scale=2):
            log_box = gr.Textbox(label="Log", lines=10, max_lines=10, interactive=False)

    coverage_popup_html = gr.HTML(value="", elem_id="coverage-popup-host")

    # Concept picker — shown after analysis when new concepts exist
    with gr.Group(visible=False) as new_concepts_group:
        gr.Markdown("**New domain concepts found in document — select which to add to next iteration:**")
        new_concepts_box = gr.CheckboxGroup(choices=[], label="", interactive=True)
        confirm_add_btn  = gr.Button("Queue selected for next iteration", variant="primary", scale=0)


    timer = gr.Timer(value=1.0)

    # Output lists
    START_OUTPUTS = [
        sid_state, chatbot, answer_box,
        answer_row, yes_no_row, challenge_row, approval_panel,
        output_box, final_validation_box, log_box,
    ]  # 10 items

    POLL_OUTPUTS = [
        chatbot,
        answer_row, yes_no_row, challenge_row, approval_panel,
        concept_lbl, chunk_box, sample_box, validation_box,
        output_box, final_validation_box, log_box,
    ]  # 12 items
    # Wiring
    start_btn.click(start, [prompt_box, sid_state], START_OUTPUTS)
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

    approve_btn.click(approve, [sid_state], [approval_panel])
    reject_btn.click( reject,  [sid_state], [approval_panel])


if __name__ == "__main__":
    share = "--share" in sys.argv
    demo.launch(server_name="0.0.0.0", server_port=7860, share=share,
               theme=gr.themes.Soft(), css=CSS)
