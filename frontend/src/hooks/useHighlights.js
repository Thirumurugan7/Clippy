import { useEffect, useState, useCallback } from "react";

// Loads stored gemma4 highlight candidates for a video and can (re)generate them
// by enqueuing the worker job and polling until it lands. Never fabricates:
// surfaces the raw model output + error when parsing failed server-side.
export function useHighlights(videoId) {
  const [status, setStatus] = useState("loading"); // loading|idle|running|ready|failed
  const [clips, setClips] = useState(null);
  const [model, setModel] = useState(null);
  const [error, setError] = useState(null);
  const [raw, setRaw] = useState(null);

  // Load any existing highlights on mount.
  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    fetch(`/api/videos/${videoId}/highlights`)
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        if (d.ready && d.clips) {
          setClips(d.clips);
          setModel(d.model);
          setStatus("ready");
        } else if (d.ready && d.error) {
          setError(d.error);
          setRaw(d.raw);
          setStatus("failed");
        } else {
          setStatus("idle");
        }
      })
      .catch(() => !cancelled && setStatus("idle"));
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  const generate = useCallback(async () => {
    setStatus("running");
    setError(null);
    const res = await fetch(`/api/videos/${videoId}/highlights`, { method: "POST" });
    if (!res.ok) {
      setStatus("failed");
      setError((await res.json().catch(() => ({}))).detail || "could not start");
      return;
    }
    const { job_id } = await res.json();
    // poll the job, then read the stored result
    function poll() {
      fetch(`/api/jobs/${job_id}`)
        .then((r) => r.json())
        .then((job) => {
          if (job.status === "done") {
            fetch(`/api/videos/${videoId}/highlights`)
              .then((r) => r.json())
              .then((d) => {
                if (d.clips) {
                  setClips(d.clips);
                  setModel(d.model);
                  setStatus("ready");
                } else {
                  setError(d.error || "model returned no usable clips");
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
    }
    poll();
  }, [videoId]);

  return { status, clips, model, error, raw, generate };
}
