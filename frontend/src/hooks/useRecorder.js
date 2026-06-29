import { useState, useRef, useCallback, useEffect } from "react";

// In-browser capture via MediaRecorder. Source is "camera" (webcam + mic) or
// "screen" (display + mic). Produces a webm Blob the existing upload pipeline
// ingests like any other source video (ffmpeg/whisper handle webm fine).
export function useRecorder() {
  const [state, setState] = useState("idle"); // idle|preview|recording|recorded|error
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [blob, setBlob] = useState(null);

  const streamRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const previewRef = useRef(null); // <video> element for live preview
  const timerRef = useRef(null);

  const stopTracks = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startPreview = useCallback(async (source) => {
    setError(null);
    setBlob(null);
    try {
      const withMic = { audio: true };
      const stream =
        source === "screen"
          ? await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true })
          : await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, ...withMic });
      // Screen capture often omits mic; add it so the clip has a voice track.
      if (source === "screen") {
        try {
          const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
          mic.getAudioTracks().forEach((t) => stream.addTrack(t));
        } catch {
          /* no mic available — keep system audio only */
        }
      }
      streamRef.current = stream;
      if (previewRef.current) {
        previewRef.current.srcObject = stream;
        previewRef.current.muted = true;
        await previewRef.current.play().catch(() => {});
      }
      setState("preview");
    } catch (e) {
      setError(e.name === "NotAllowedError" ? "Permission denied — allow camera/screen access." : String(e.message || e));
      setState("error");
    }
  }, []);

  const start = useCallback(() => {
    if (!streamRef.current) return;
    chunksRef.current = [];
    const mime = MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")
      ? "video/webm;codecs=vp9,opus"
      : "video/webm";
    const rec = new MediaRecorder(streamRef.current, { mimeType: mime });
    rec.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
    rec.onstop = () => {
      setBlob(new Blob(chunksRef.current, { type: "video/webm" }));
      setState("recorded");
    };
    rec.start();
    recorderRef.current = rec;
    setElapsed(0);
    timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    setState("recording");
  }, []);

  const stop = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
    stopTracks();
  }, [stopTracks]);

  const reset = useCallback(() => {
    stop();
    setBlob(null);
    setElapsed(0);
    setState("idle");
  }, [stop]);

  useEffect(() => stopTracks, [stopTracks]); // clean up on unmount

  return { state, error, elapsed, blob, previewRef, startPreview, start, stop, reset };
}
