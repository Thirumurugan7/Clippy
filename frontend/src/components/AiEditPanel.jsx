import { useState } from "react";
import { useAiEdit } from "../hooks/useAiEdit.js";

function fmt(t) {
  const m = Math.floor(t / 60);
  const s = Math.round(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Conversational AI edit: describe a clip, then refine in follow-ups ("make it
// shorter", "start at the joke"). Each AI turn is applyable to the editor.
export function AiEditPanel({ videoId, onApply }) {
  const { status, turns, error, run } = useAiEdit(videoId);
  // A use-case template chosen on the home screen leaves a starter prompt here.
  // Read-only (no removeItem) so React StrictMode's double-mount stays pure; the
  // stash is keyed by videoId and harmlessly overwritten per template use.
  const [prompt, setPrompt] = useState(() => sessionStorage.getItem(`clippy_prompt_${videoId}`) || "");

  const started = turns.length > 0 || status !== "idle";
  const placeholder = started
    ? "Refine it — e.g. make it 10s shorter, or start at the hook"
    : "Describe the clip — e.g. a 40s TikTok of the funniest moment";

  function send() {
    const p = prompt.trim();
    if (!p || status === "running") return;
    run(p);
    setPrompt("");
  }

  return (
    <div className="panel ai-panel">
      <h3>AI edit</h3>
      <p className="panel-sub">
        Describe a clip, then keep refining. The AI remembers the conversation.
      </p>

      <div className="ai-thread">
        {turns.length === 0 && status === "idle" && (
          <div className="ai-empty">
            <p className="muted">Try: “Make a 30s reel of the strongest point.”</p>
            <p className="muted">Then: “Tighten it” or “Use a bolder caption.”</p>
          </div>
        )}

        {turns.map((t) => (
          <div className="ai-turn" key={t.id}>
            <div className="ai-bubble ai-you">{t.prompt}</div>
            {t.proposal ? (
              <div className="ai-bubble ai-bot">
                <p className="mono ai-clipline">
                  {fmt(t.proposal.clip.start)}–{fmt(t.proposal.clip.end)} ·{" "}
                  {Math.round(t.proposal.clip.end - t.proposal.clip.start)}s ·{" "}
                  {t.proposal.aspect} · {t.proposal.caption_preset}
                </p>
                {t.proposal.reason && <p className="ai-reason">{t.proposal.reason}</p>}
                <button className="btn-amber full" onClick={() => onApply(t.proposal)}>
                  Apply to editor
                </button>
              </div>
            ) : (
              <div className="ai-bubble ai-bot error">
                Couldn’t build a clip from that. Try rephrasing.
              </div>
            )}
          </div>
        ))}

        {status === "running" && <div className="ai-bubble ai-bot mono">Thinking…</div>}
        {status === "failed" && error && <p className="mono error">{error}</p>}
      </div>

      <div className="ai-composer">
        <textarea
          className="ai-input"
          rows={2}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send();
          }}
          placeholder={placeholder}
        />
        <button className="btn-amber full" onClick={send} disabled={status === "running" || !prompt.trim()}>
          {status === "running" ? "Thinking…" : started ? "Refine" : "Generate edit"}
        </button>
        <p className="ai-hint mono">⌘/Ctrl + Enter to send</p>
      </div>
    </div>
  );
}
