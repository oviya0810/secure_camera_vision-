# Secure Camera Network — Dashboard

Colourful dark-theme Flask dashboard for your Secure Camera Network.
No Streamlit. Add cameras by pasting their stream link, watch live feeds with
YOLO object detection, and get tamper / feed-loss / network-anomaly alerts
with live graphs.

## What it does

- **Add cameras by link** — paste `http://pi.local:8080/video`,
  `http://pi1.local:8080/video`, etc. Add as many as you want. They are saved,
  so they come back after a restart.
- **Laptop webcam** — one click adds `webcam:0`.
- **Live view + detection** — each feed is pulled in, YOLOv8 draws boxes, and
  object counts feed the graphs.
- **Tamper / attack detection** (the demo): the system watches each feed and
  raises a red alert for
  - `FEED_LOSS` — camera unplugged / stream cut
  - `BLACK_FRAME` — lens covered / signal cut
  - `FROZEN_FEED` — identical frames repeating (replay / still image)
  - `NETWORK_ANOMALY` — the camera host stops responding / high latency
- **Trust score** per camera = feed health + network health + detection
  confidence, shown live and dropping to red when something is wrong.
- **Graphs** — live trust, detections per camera, feed-vs-network health, FPS.

> How to demo an "attack": cover the lens, unplug the USB camera, or pull the
> Pi's network — the matching alert turns the card red and logs it. The
> dashboard detects real problems in the feed; it does not fabricate feeds.

## Run it (Windows laptop)

```powershell
cd dashboard
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Linux / Mac:

```bash
cd dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:8501**

First run downloads the YOLOv8n model (needs internet once). If it can't,
detection just stays **OFF** and everything else still works. To pre-place the
model, drop `yolov8n.pt` next to `app.py`.

## Using it

1. Start your Pi camera node (it must be streaming at `http://pi.local:8080`).
2. In the dashboard, paste `http://pi.local:8080/video` → **Add link**.
3. Add a second Pi the same way: `http://pi1.local:8080/video`.
4. **Add laptop webcam** for a local camera.
5. Watch the feeds, trust scores and alerts update live.

If `pi.local` doesn't resolve on your laptop, use the Pi's IP instead, e.g.
`http://192.168.1.25:8080/video`.

## Files

| File | What it is |
| --- | --- |
| `app.py` | Flask app + routes + MJPEG proxy |
| `camera_manager.py` | pulls frames, runs detection + integrity, trust score, network probe |
| `detector.py` | YOLOv8 wrapper (degrades to OFF if model missing) |
| `integrity.py` | feed tamper analysis (freeze / black / loss) |
| `templates/index.html` | dashboard page |
| `static/style.css` | dark colourful theme |
| `static/app.js` | live updates + charts |
| `static/chart.umd.min.js` | Chart.js, bundled so it works offline |
| `data/cameras.json` | saved camera list (created on first add) |

## Notes

- Runs fully on your laptop/LAN. The Pi only streams video; detection and
  analysis run here, so the Pi stays light.
- Default port is **8501**. Change `PORT` at the top of `app.py` if needed.
