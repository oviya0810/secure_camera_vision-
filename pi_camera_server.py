#!/usr/bin/env python3
"""
pi_camera_server.py  -  Secure Camera Network : Raspberry Pi camera node

Runs on the Raspberry Pi with a USB webcam and publishes the live feed on
the local network so the laptop server/dashboard can add it just by URL:

    http://pi.local:8080            -> test page (open in any browser)
    http://pi.local:8080/video      -> live MJPEG stream (used by dashboard)
    http://pi.local:8080/snapshot.jpg -> single JPEG frame
    http://pi.local:8080/health     -> JSON status (node id, fps, camera ok)

Object detection (YOLO) runs on the laptop, not here, so the Pi only needs
OpenCV + Flask and stays fast.

Usage:
    python pi_camera_server.py                      # camera 0, port 8080
    python pi_camera_server.py --camera 1 --port 8080 --width 640 --height 480
    python pi_camera_server.py --camera test.mp4    # stream a video file instead

Optional access key (recommended outside the lab):
    python pi_camera_server.py --key mysecret
    -> dashboard URL becomes  http://pi.local:8080/video?key=mysecret
"""

import argparse
import os
import socket
import threading
import time

import cv2
from flask import Flask, Response, jsonify, request, abort

# ---------------------------------------------------------------- arguments

parser = argparse.ArgumentParser(description="Pi camera stream node")
parser.add_argument("--camera", default=os.getenv("CAMERA_INDEX", "0"),
                    help="camera index (0, 1, ...) or a video file path")
parser.add_argument("--port", type=int, default=int(os.getenv("STREAM_PORT", "8080")))
parser.add_argument("--width", type=int, default=int(os.getenv("CAMERA_WIDTH", "640")))
parser.add_argument("--height", type=int, default=int(os.getenv("CAMERA_HEIGHT", "480")))
parser.add_argument("--fps", type=int, default=int(os.getenv("CAMERA_FPS", "15")))
parser.add_argument("--quality", type=int, default=int(os.getenv("JPEG_QUALITY", "70")))
parser.add_argument("--node-id", default=os.getenv("CAMERA_NODE_ID", socket.gethostname()))
parser.add_argument("--key", default=os.getenv("STREAM_KEY", ""),
                    help="optional access key; clients must add ?key=<key>")
args = parser.parse_args()

SOURCE = int(args.camera) if str(args.camera).isdigit() else args.camera
IS_FILE = not isinstance(SOURCE, int)


# ---------------------------------------------------------------- camera thread

class Camera:
    """Single capture thread shared by every viewer. Reconnects automatically
    if the USB camera is unplugged / replugged."""

    def __init__(self):
        self.lock = threading.Lock()
        self.jpeg = None
        self.ok = False
        self.frames = 0
        self.fps_measured = 0.0
        self.last_frame_time = 0.0
        self.started = time.time()
        self.error = ""
        threading.Thread(target=self._loop, daemon=True).start()

    def _open(self):
        if IS_FILE:
            cap = cv2.VideoCapture(SOURCE)
        else:
            cap = cv2.VideoCapture(SOURCE, cv2.CAP_V4L2)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
            cap.set(cv2.CAP_PROP_FPS, args.fps)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _loop(self):
        delay = 1.0 / max(args.fps, 1)
        count, t0 = 0, time.time()
        while True:
            cap = self._open()
            if not cap.isOpened():
                self.ok, self.error = False, f"cannot open camera {SOURCE}"
                print(f"[camera] {self.error} - retrying in 3 s")
                time.sleep(3)
                continue
            print(f"[camera] opened source {SOURCE}")
            self.error = ""
            while True:
                start = time.time()
                ok, frame = cap.read()
                if not ok:
                    if IS_FILE:                       # loop the video file
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    self.ok, self.error = False, "frame read failed (camera unplugged?)"
                    print(f"[camera] {self.error} - reconnecting")
                    break
                if frame.shape[1] != args.width or frame.shape[0] != args.height:
                    frame = cv2.resize(frame, (args.width, args.height))
                enc_ok, buf = cv2.imencode(".jpg", frame,
                                           [cv2.IMWRITE_JPEG_QUALITY, args.quality])
                if enc_ok:
                    with self.lock:
                        self.jpeg = buf.tobytes()
                        self.ok = True
                        self.frames += 1
                        self.last_frame_time = time.time()
                count += 1
                if time.time() - t0 >= 2:
                    self.fps_measured = round(count / (time.time() - t0), 1)
                    count, t0 = 0, time.time()
                sleep = delay - (time.time() - start)
                if sleep > 0:
                    time.sleep(sleep)
            cap.release()
            time.sleep(1)

    def get_jpeg(self):
        with self.lock:
            return self.jpeg


camera = Camera()
app = Flask(__name__)


def check_key():
    if args.key and request.args.get("key") != args.key:
        abort(401)


# ---------------------------------------------------------------- routes

@app.route("/")
def index():
    check_key()
    q = f"?key={args.key}" if args.key else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{args.node_id} - camera node</title>
<style>body{{background:#111;color:#eee;font-family:sans-serif;text-align:center;margin:0;padding:16px}}
img{{max-width:100%;border:2px solid #444;border-radius:8px}}code{{color:#7fd}}</style></head>
<body><h2>{args.node_id} &middot; live feed</h2>
<img src="/video{q}" alt="live stream">
<p>Stream URL for dashboard: <code>http://{socket.gethostname()}.local:{args.port}/video{q}</code></p>
<p><a style="color:#7fd" href="/health{q}">/health</a></p></body></html>"""


@app.route("/video")
def video():
    check_key()

    def gen():
        last = None
        while True:
            frame = camera.get_jpeg()
            if frame is None or frame is last:
                time.sleep(0.01)
                continue
            last = frame
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n"
                   b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                   + frame + b"\r\n")

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/snapshot.jpg")
def snapshot():
    check_key()
    frame = camera.get_jpeg()
    if frame is None:
        abort(503)
    return Response(frame, mimetype="image/jpeg")


@app.route("/health")
def health():
    check_key()
    age = time.time() - camera.last_frame_time if camera.last_frame_time else None
    return jsonify({
        "node_id": args.node_id,
        "hostname": socket.gethostname(),
        "camera_ok": camera.ok and age is not None and age < 3,
        "source": str(SOURCE),
        "resolution": f"{args.width}x{args.height}",
        "fps": camera.fps_measured,
        "frames_sent": camera.frames,
        "last_frame_age_s": round(age, 2) if age is not None else None,
        "uptime_s": int(time.time() - camera.started),
        "error": camera.error,
        "auth": bool(args.key),
    })


if __name__ == "__main__":
    host = socket.gethostname()
    print("=" * 60)
    print(f" Camera node : {args.node_id}")
    print(f" Source      : {SOURCE}  ({args.width}x{args.height} @ {args.fps} fps)")
    print(f" Test page   : http://{host}.local:{args.port}/")
    print(f" Stream URL  : http://{host}.local:{args.port}/video")
    print(f" Health      : http://{host}.local:{args.port}/health")
    print("=" * 60)
    app.run(host="0.0.0.0", port=args.port, threaded=True)
