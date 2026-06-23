import { useState, useCallback } from "react";

// Runs a plain-English edit instruction through gemma4 (worker job) and returns
// a reviewable proposal: {clip, aspect, caption_preset, reason}.
export function useAiEdit(videoId) {
  const [status, setStatus] = useState("idle"); // idle|running|ready|failed
  const [proposal, setProposal] = useState(null);
  const [error, setError] = useState(null);
  const [raw, setRaw] = useState(null);

  const run = useCallback(async (prompt) => {
    setStatus("running");
    setError(null);
    setProposal(null);
    const res = await fetch(`/api/videos/${videoId}/ai_edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok) {
      setStatus("failed");
      setError("could not start");
      return;
    }
    const { job_id } = await res.json();
    (function poll() {
      fetch(`/api/jobs/${job_id}`)
        .then((r) => r.json())
        .then((job) => {
          if (job.status === "done") {
            fetch(`/api/videos/${videoId}/ai_edit`)
              .then((r) => r.json())
              .then((d) => {
                if (d.clip) {
                  setProposal(d);
                  setStatus("ready");
                } else {
                  setError(d.error || "no usable edit");
                  setRaw(d.raw);
                  setStatus("failed");
                }
              });
          } else if (job.status === "failed") {
            setError(job.error);
            setStatus("failed");
          } else {
            setTimeout(poll, 1500);
          }
        });
    })();
  }, [videoId]);

  return { status, proposal, error, raw, run };
}
