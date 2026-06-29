import { useState, useCallback, useEffect } from "react";

// Conversational plain-English editing. Each prompt is a worker job; the model
// refines on prior turns server-side. We keep the running thread of turns
// ({prompt, proposal|error}) so the panel reads like a chat.
export function useAiEdit(videoId) {
  const [status, setStatus] = useState("idle"); // idle|running|ready|failed
  const [turns, setTurns] = useState([]);
  const [error, setError] = useState(null);

  const loadTurns = useCallback(async () => {
    try {
      const r = await fetch(`/api/videos/${videoId}/ai_edit/turns`);
      const d = await r.json();
      setTurns(d.turns || []);
    } catch {
      /* leave as-is */
    }
  }, [videoId]);

  useEffect(() => {
    loadTurns();
  }, [loadTurns]);

  const run = useCallback(
    async (prompt) => {
      setStatus("running");
      setError(null);
      const res = await fetch(`/api/videos/${videoId}/ai_edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      if (!res.ok) {
        setStatus("failed");
        setError("Couldn't start — is the transcript ready?");
        return;
      }
      const { job_id } = await res.json();
      (function poll() {
        fetch(`/api/jobs/${job_id}`)
          .then((r) => r.json())
          .then(async (job) => {
            if (job.status === "done") {
              await loadTurns();
              setStatus("ready");
            } else if (job.status === "failed") {
              setError(job.error);
              setStatus("failed");
            } else {
              setTimeout(poll, 1500);
            }
          });
      })();
    },
    [videoId, loadTurns]
  );

  // Latest proposal (for callers that just want the most recent clip).
  const last = turns[turns.length - 1];
  const proposal = last && last.proposal ? last.proposal : null;

  return { status, turns, proposal, error, run };
}
