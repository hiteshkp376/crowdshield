# CrowdShield — Live Camera Demo

For your Aug 23 submission: uses your **normal webcam** (not real
thermal hardware — see honesty note below) to drive the real detection
pipeline live, feeding Module D → Module E automatically, so the
dashboard updates as it sees you move in front of the camera.

## Setup

```bash
pip install opencv-python requests --break-system-packages
```

(You already have `opencv-python-headless` from other modules —
`opencv-python` includes the GUI window support needed for `cv2.imshow`
here, which the headless version doesn't have. Install both if unsure;
they won't conflict.)

## Before running

1. Start Module A (8001), C (8003), D (8004), E (8005)
2. Run the dashboard's **"RUN FULL ANALYSIS"** at least once — this
   script fetches the current venue's real zone data from Module A, so
   there needs to be one to fetch

## Run

```bash
cd live_demo
python live_camera_worker.py --zone-id Z1
```

Replace `Z1` with whichever zone_id your camera should represent (check
the dashboard's Zone Risk panel for valid IDs after running analysis).

**Controls:**
- `q` — quit
- `t` — toggle the simulated-thermal-style view

## What happens

- Every ~2 seconds, it runs **real HOG person detection** and **real
  Farneback optical flow** (the exact same functions already tested in
  Module D) on your webcam feed
- Automatically POSTs the result to Module D, then Module E — so escalation
  events, the Pending Escalations panel, and Digital Twin colors all
  update live, without touching the dashboard's manual Signal Injector
- The dashboard now **auto-polls** Module D's history every 5 seconds
  (new addition), so you'll see the map update on its own as the script
  runs — no manual "Feed to Fusion Engine" clicks needed for this demo

## HONEST LABELING — say this in your demo/pitch

This uses a **normal webcam**, not real thermal hardware. Pressing `t`
shows a color-mapped recoloring of the normal feed for visual effect —
it is clearly labeled on-screen as simulated, and it is **not** real
thermal sensor data. This is consistent with the project's stated
hackathon-scale constraint (see Module D's README): real thermal/
pressure hardware isn't available, so this demo mode shows the
detection pipeline working live using equipment you actually have.

## What's genuinely tested vs. what isn't

- **Detection + scoring logic** (`live_processing.py`): rigorously
  tested with synthetic motion frames — confirmed correct density
  calculation, correct optical flow direction detection, correct
  reverse-flow detection, and the payload exactly matches Module D's
  real expected schema.
- **HTTP helper functions** (fetching zone area from Module A, safe
  threshold from Module C): tested against the real running backend —
  confirmed correct data returned, confirmed correct error handling for
  an invalid zone_id.
- **The actual camera-capture loop** (`cv2.VideoCapture`,
  `cv2.imshow`): could NOT be tested — no camera hardware exists in the
  environment this was built in. Verified the file has valid Python
  syntax (`py_compile`) and the argument parser works correctly, but
  the live capture itself is your first real test.

## If the camera won't open

- Try `--camera-index 1` (sometimes 0 isn't the right device)
- Make sure no other app (Zoom, Teams, another CV script) is currently
  using the webcam
- On Windows, check Settings → Privacy → Camera → allow desktop apps

## Troubleshooting a slow/laggy feed

HOG detection is the expensive part. If the preview window feels
sluggish, increase `--report-interval-s` (e.g. `--report-interval-s 4`)
— the camera preview itself still runs at full speed; only the
detection/reporting step is throttled.
