"""Run gemma4 highlight detection on a real video's transcript and print the
raw model JSON + the parsed clips. M3 step 1: inspect the actual output before
building any UI.

Usage: ./.venv/bin/python scripts/run_highlights.py <video_id> [N]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.highlights import detect_highlights

video_id = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 5

res = detect_highlights(video_id, n=n)

print(f"model: {res['model']}  retried: {res['retried']}")
print("\n===== RAW gemma4 OUTPUT =====")
print(res["raw"])
print("\n===== PARSED CLIPS =====")
if res["clips"] is None:
    print("PARSE FAILED (no clips fabricated). error:", res.get("error"))
else:
    print(json.dumps(res["clips"], indent=2))
    print(f"\n{len(res['clips'])} valid candidate clip(s).")
