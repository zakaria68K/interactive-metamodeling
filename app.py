import datetime
import json
import queue
import sys
import threading
import uuid
from pathlib import Path

import gradio as gr

from metaLoop.metamodeling_agent import MetamodelingAgent

class _Session:
    def __init__(self):
        # Elicitation Q&A
        self.elicit_q: queue.Queue[str] = queue.Queue()
        self.elicit_a: queue.Queue[str] = queue.Queue()
        self.waiting_elicitation: bool = False

        # Chunk approval
        self.approval_q: queue.Queue[dict] = queue.Queue()
        self.approval_a: queue.Queue[bool] = queue.Queue()
        self.waiting_approval: bool = False
        self.pending_payload: dict | None = None

        # Final result
        self.result_q: queue.Queue[dict] = queue.Queue()
        self.final_result: dict | None = None

        # UI state
        self.chat: list[dict] = []
        self.log: list[str] = []


_sessions: dict[str, _Session] = {}


def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


# ──────────────────────────────────────────────────────────────────────────────
# Agent thread
# ──────────────────────────────────────────────────────────────────────────────

def _run_agent(sess: _Session, prompt: str) -> None:
    agent = MetamodelingAgent()

    def user_responder(question: str, context: dict) -> str:
        # If concepts are proposed, show them in the chat first
        if "proposed_concepts" in context:
            raw = context.get("proposed_concepts_raw")
            if raw and isinstance(raw, list) and isinstance(raw[0], dict):
                lines = []
                for c in raw:
                    name = c.get("name", "")
                    desc = c.get("description", "")
                    lines.append(f"• **{name}**: {desc}" if desc else f"• {name}")
                concepts_text = "\n".join(lines)
            else:
                concepts = context.get("proposed_concepts", [])
                concepts_text = "\n".join(f"• {c}" for c in concepts)
            sess.chat.append({
                "role": "assistant",
                "content": f"**Proposed concepts:**\n{concepts_text}",
            })

        sess.chat.append({"role": "assistant", "content": question})
        sess.log.append(f"[{_ts()}] Elicitation: {question[:80]}")
        sess.waiting_elicitation = True
        sess.elicit_q.put(question)
        answer = sess.elicit_a.get(block=True)
        sess.waiting_elicitation = False
        sess.chat.append({"role": "user", "content": answer})
        return answer

    def human_validator(payload: dict) -> bool:
        sess.log.append(f"[{_ts()}] Awaiting approval for concept: {payload.get('concept', '')}")
        sess.pending_payload = payload
        sess.waiting_approval = True
        sess.approval_q.put(payload)
        decision = sess.approval_a.get(block=True)
        sess.waiting_approval = False
        sess.log.append(f"[{_ts()}] {'Approved' if decision else 'Rejected'}: {payload.get('concept', '')}")
        return decision

    try:
        result = agent.run_iterative(
            prompt,
            human_validator=human_validator,
            user_responder=user_responder,
        )
        sess.log.append(f"[{_ts()}] Pipeline complete.")
        _save_session(sess, result)
        sess.result_q.put(result)
    except Exception as exc:  # noqa: BLE001
        sess.log.append(f"[{_ts()}] Error: {exc}")
        sess.result_q.put({"final_metamodel": f"# ERROR\n{exc}", "concepts": []})


def _save_session(sess: _Session, result: dict) -> None:
    out_dir = Path("session_logs")
    out_dir.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    data = {
        "timestamp": ts,
        "log": sess.log,
        "chat": sess.chat,
        "concepts": result.get("concepts", []),
        "final_metamodel": result.get("final_metamodel", ""),
    }
    (out_dir / f"session_{ts}.json").write_text(json.dumps(data, indent=2))


# ──────────────────────────────────────────────────────────────────────────────
# Gradio event handlers
# ──────────────────────────────────────────────────────────────────────────────

def start(prompt: str, sid: str):
    if not prompt.strip():
        return (
            sid,
            [],
            "",
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value=""),
            "Enter a prompt first.",
        )

    new_sid = str(uuid.uuid4())
    sess = _Session()
    sess.log.append(f"[{_ts()}] Started: {prompt[:80]}")
    sess.chat.append({
        "role": "assistant",
        "content": f"Starting metamodel generation for: **{prompt}**\n\nI'll ask a few questions to understand the domain.",
    })
    _sessions[new_sid] = sess

    threading.Thread(target=_run_agent, args=(sess, prompt), daemon=True).start()

    return (
        new_sid,
        list(sess.chat),
        "",
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(value=""),
        f"[{_ts()}] Pipeline started…",
    )


def poll(sid: str):
    """Called by gr.Timer every second to refresh all dynamic UI elements."""
    empty = (
        gr.update(), gr.update(), gr.update(),
        gr.update(), gr.update(), gr.update(), gr.update(),
        gr.update(), gr.update(),
    )
    if not sid or sid not in _sessions:
        return empty

    sess = _sessions[sid]
    log_text = "\n".join(sess.log[-20:])  # last 20 lines

    # Consume any new elicitation question signal (content already in sess.chat)
    try:
        sess.elicit_q.get_nowait()
    except queue.Empty:
        pass

    # Check for finished result
    try:
        sess.final_result = sess.result_q.get_nowait()
    except queue.Empty:
        pass

    if sess.final_result is not None:
        return (
            list(sess.chat),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(value=sess.final_result.get("final_metamodel", "")),
            log_text,
        )

    # Approval panel
    if sess.waiting_approval and sess.pending_payload:
        p = sess.pending_payload
        return (
            list(sess.chat),
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(value=p.get("concept", "")),
            gr.update(value=p.get("chunk", "")),
            gr.update(value=p.get("sample_model", "")),
            gr.update(value=p.get("validation", {})),
            gr.update(),
            log_text,
        )

    # Elicitation answer row
    return (
        list(sess.chat),
        gr.update(visible=sess.waiting_elicitation),
        gr.update(visible=False),
        gr.update(), gr.update(), gr.update(), gr.update(),
        gr.update(),
        log_text,
    )


def submit_answer(answer: str, sid: str):
    if sid in _sessions and answer.strip():
        _sessions[sid].elicit_a.put(answer.strip())
    return "", gr.update(visible=False)


def approve(sid: str):
    if sid in _sessions:
        _sessions[sid].approval_a.put(True)
    return gr.update(visible=False)


def reject(sid: str):
    if sid in _sessions:
        _sessions[sid].approval_a.put(False)
    return gr.update(visible=False)


# ──────────────────────────────────────────────────────────────────────────────
# UI layout
# ──────────────────────────────────────────────────────────────────────────────

with gr.Blocks(title="Interactive Metamodel Generator") as demo:
    sid_state = gr.State("")

    gr.Markdown(
        "# Interactive Metamodel Generator\n"
        "Describe a software domain in plain language. "
        "The system will ask you questions to understand your domain, then generate a JjScript metamodel "
        "concept-by-concept — asking for your approval at each step."
    )

    with gr.Row():
        prompt_box = gr.Textbox(
            label="Domain prompt",
            placeholder="e.g. A university course management system",
            scale=4,
        )
        start_btn = gr.Button("▶ Start", variant="primary", scale=1)

    # Elicitation chat
    chatbot = gr.Chatbot(label="Domain elicitation", height=280)

    with gr.Row(visible=False) as answer_row:
        answer_box = gr.Textbox(
            label="Your answer",
            placeholder="Type your answer and press Enter or Submit",
            scale=4,
            interactive=True,
        )
        submit_btn = gr.Button("Submit", variant="primary", scale=1)

    # Chunk approval panel
    with gr.Group(visible=False) as approval_panel:
        gr.Markdown("### ✏️ Review generated chunk — Approve or Reject")
        concept_box = gr.Textbox(label="Concept", interactive=False)
        with gr.Row():
            chunk_box = gr.Code(label="Generated chunk (JjScript)", language="python", lines=12)
            sample_box = gr.Code(label="Sample model instance", language="python", lines=12)
        validation_box = gr.JSON(label="Auto-validation result")
        with gr.Row():
            approve_btn = gr.Button("Approve", variant="primary", scale=1)
            reject_btn = gr.Button("Reject", variant="stop", scale=1)

    # Progress + output
    with gr.Row():
        log_box = gr.Textbox(label="Progress log", lines=6, interactive=False, scale=2)
        output_box = gr.Code(
            label="Final metamodel (JjScript)",
            language="python",
            lines=20,
            scale=3,
            interactive=False,
        )

    timer = gr.Timer(value=1.0)

    # ── output lists ──────────────────────────────────────────────────────────
    START_OUTPUTS = [
        sid_state,
        chatbot,
        answer_box,
        answer_row,
        approval_panel,
        output_box,
        log_box,
    ]
    POLL_OUTPUTS  = [chatbot, answer_row, approval_panel,
                     concept_box, chunk_box, sample_box, validation_box,
                     output_box, log_box]

    # ── wiring ────────────────────────────────────────────────────────────────
    start_btn.click(start, inputs=[prompt_box, sid_state], outputs=START_OUTPUTS)

    timer.tick(poll, inputs=[sid_state], outputs=POLL_OUTPUTS)

    submit_btn.click(submit_answer, inputs=[answer_box, sid_state], outputs=[answer_box, answer_row])
    answer_box.submit(submit_answer, inputs=[answer_box, sid_state], outputs=[answer_box, answer_row])

    approve_btn.click(approve, inputs=[sid_state], outputs=[approval_panel])
    reject_btn.click(reject, inputs=[sid_state], outputs=[approval_panel])


if __name__ == "__main__":
    share = "--share" in sys.argv
    demo.launch(server_name="0.0.0.0", server_port=7860, share=share, theme=gr.themes.Soft())