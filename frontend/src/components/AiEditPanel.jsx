import { useState } from "react";
import { useAiEdit } from "../hooks/useAiEdit.js";

function fmt(t) {
  const m = Math.floor(t / 60);
  const s = Math.round(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Type an instruction; gemma4 proposes a clip + aspect + caption preset; you
// apply it (sets the EDL + settings) and adjust before exporting.
export function AiEditPanel({ videoId, onApply }) {
  const { status, proposal, error, raw, run } = useAiEdit(videoId);
  const [prompt, setPrompt] = useState("Make a 40s Instagram reel from the best part");

  return (
    <div className="panel">
      <h3>AI edit</h3>
      <p className="panel-sub">Describe the clip you want. The AI proposes it; you review and export.</p>
      <textarea
        className="ai-input"
        rows={3}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="e.g. make a 30s TikTok of the funniest moment"
      />
      <button className="btn-amber full" onClick={() => run(prompt)} disabled={status === "running"}>
        {status === "running" ? "Thinking…" : "Generate edit"}
      </button>

      {status === "failed" && (
        <div className="ai-result">
          <p className="error">Couldn't build an edit.</p>
          {error && <p className="mono error">{error}</p>}
          {raw && <details><summary className="mono">raw</summary><pre className="raw">{raw}</pre></details>}
        </div>
      )}

      {status === "ready" && proposal && (
        <div className="ai-result">
          <p className="mono">
            {fmt(proposal.clip.start)}–{fmt(proposal.clip.end)} ·{" "}
            {Math.round(proposal.clip.end - proposal.clip.start)}s · {proposal.aspect} ·{" "}
            {proposal.caption_preset}
          </p>
          <p className="ai-reason">{proposal.reason}</p>
          <button className="btn-amber full" onClick={() => onApply(proposal)}>Apply to editor</button>
        </div>
      )}
    </div>
  );
}
