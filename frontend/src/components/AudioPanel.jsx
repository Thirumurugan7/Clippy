// Audio cleanup controls. The toggle drives the per-video `enhance_audio`
// setting, applied at export time (denoise + loudness normalize to the -16 LUFS
// social target). Preview is silent on processing, so we describe the effect.
export function AudioPanel({ settings, setSettings }) {
  const on = !!settings.enhance_audio;
  return (
    <div className="panel">
      <h3>Audio</h3>
      <p className="panel-sub">Clean up voice and even out loudness on export.</p>

      <button
        className={"toggle-row" + (on ? " on" : "")}
        onClick={() => setSettings({ enhance_audio: !on })}
        aria-pressed={on}
      >
        <span className="toggle-text">
          <span className="toggle-title">Enhance audio</span>
          <span className="toggle-desc">Reduce background noise and normalize volume</span>
        </span>
        <span className={"switch" + (on ? " on" : "")} aria-hidden>
          <span className="switch-knob" />
        </span>
      </button>

      <ul className="audio-detail">
        <li>High-pass filter removes low rumble and hum</li>
        <li>FFT denoiser softens steady background noise</li>
        <li>Loudness normalized to -16 LUFS (TikTok/Reels target)</li>
      </ul>
      <p className="panel-foot mono">
        {on ? "On — applied to every export." : "Off — exports use the original audio."}
      </p>
    </div>
  );
}
