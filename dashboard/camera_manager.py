"""
camera_manager.py - holds every camera the user adds, pulls frames from it,
runs YOLO + integrity, measures network health, and keeps rolling stats /
history for the dashboard graphs.

A camera source can be:
  - an MJPEG URL from a Pi node   e.g. http://pi.local:8080/video
  - a laptop webcam index          e.g. "webcam:0"
  - a video file path (for testing)
"""

import json
import os
import threading
import time
import urllib.parse
from collections import deque

import cv2
import numpy as np
import requests

from integrity import IntegrityAnalyzer

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STORE = os.path.join(DATA_DIR, "cameras.json")

# trust fusion weights (feed + network + content)
W_FEED, W_NET, W_CONTENT = 0.5, 0.3, 0.2


def _placeholder(text, w=640, h=480):
    img = np.full((h, w, 3), 24, dtype=np.uint8)
    cv2.putText(img, text, (24, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (80, 80, 240), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


class Camera:
    def __init__(self, cam_id, name, source, detector):
        self.id = cam_id
        self.name = name
        self.source = source
        self.detector = detector
        self.integrity = IntegrityAnalyzer()

        self.lock = threading.Lock()
        self.jpeg = _placeholder("connecting...")
        self.running = True

        self.status = "connecting"
        self.fps = 0.0
        self.latency_ms = None
        self.net_ok = False
        self.det_count = 0
        self.det_labels = {}
        self.feed_health = 1.0
        self.net_health = 0.0
        self.content_health = 0.0
        self.trust = 0.0
        self.alerts = []
        self.last_ok = 0.0

        self.history = deque(maxlen=60)   # (ts, trust, fps, det, feed, net)
        threading.Thread(target=self._loop, daemon=True).start()

    # ------------------------------------------------------------------ source
    def _open_capture(self):
        if self.source.startswith("webcam:"):
            idx = int(self.source.split(":", 1)[1] or 0)
            return cv2.VideoCapture(idx)
        if self.source.startswith("http"):
            return cv2.VideoCapture(self.source)
        return cv2.VideoCapture(self.source)   # file path

    def _host(self):
        if self.source.startswith("http"):
            return urllib.parse.urlparse(self.source).hostname
        return None

    # ------------------------------------------------------------------ network
    def _probe_network(self):
        host = self._host()
        if not host:
            # local webcam - no network segment
            self.net_ok, self.latency_ms, self.net_health = True, 0, 1.0
            return
        base = self.source.rsplit("/", 1)[0]
        for path in ("/health", "/"):
            try:
                t0 = time.time()
                r = requests.get(base + path, timeout=2)
                self.latency_ms = int((time.time() - t0) * 1000)
                self.net_ok = r.status_code == 200
                # health: fast = 1.0, >800ms = poor
                self.net_health = max(0.0, 1.0 - self.latency_ms / 800.0) if self.net_ok else 0.0
                return
            except Exception:  # noqa: BLE001
                continue
        self.net_ok, self.latency_ms, self.net_health = False, None, 0.0

    # ------------------------------------------------------------------ main loop
    def _loop(self):
        last_net = 0.0
        frames, t0 = 0, time.time()
        cap = None
        while self.running:
            if cap is None or not cap.isOpened():
                cap = self._open_capture()
                if not cap.isOpened():
                    self._handle_no_frame("cannot open source")
                    time.sleep(2)
                    continue

            ok, frame = cap.read()
            if not ok or frame is None:
                if not self.source.startswith("webcam:") and not self.source.startswith("http"):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)   # loop a video file
                    continue
                self._handle_no_frame("no frame")
                cap.release()
                cap = None
                time.sleep(1)
                continue

            if frame.shape[1] > 640:
                frame = cv2.resize(frame, (640, int(frame.shape[0] * 640 / frame.shape[1])))

            frame, detections = self.detector.detect(frame)
            integ = self.integrity.update(frame)

            self._stamp(frame, integ)
            ok_enc, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok_enc:
                with self.lock:
                    self.jpeg = buf.tobytes()

            # content health from detection confidence
            self.det_count = len(detections)
            labels = {}
            for d in detections:
                labels[d["label"]] = labels.get(d["label"], 0) + 1
            self.det_labels = labels
            self.content_health = min(1.0, 0.6 + 0.1 * len(detections)) if detections else 0.6

            self.feed_health = integ["feed_health"]
            self.alerts = list(integ["alerts"])
            self.status = "online"
            self.last_ok = time.time()

            # network probe every 4 s
            if time.time() - last_net > 4:
                self._probe_network()
                last_net = time.time()
                if not self.net_ok and self._host():
                    self.alerts.append("NETWORK_ANOMALY")

            self._update_trust()

            frames += 1
            if time.time() - t0 >= 1.5:
                self.fps = round(frames / (time.time() - t0), 1)
                frames, t0 = 0, time.time()

            self.history.append({
                "t": round(time.time(), 1), "trust": self.trust, "fps": self.fps,
                "det": self.det_count, "feed": self.feed_health, "net": self.net_health,
            })

    def _handle_no_frame(self, why):
        integ = self.integrity.update(None)
        self.feed_health = integ["feed_health"]
        self.status = "offline"
        self.alerts = ["FEED_LOSS"]
        self._probe_network()
        self._update_trust()
        with self.lock:
            self.jpeg = _placeholder(f"{self.name}: {why}")
        self.history.append({
            "t": round(time.time(), 1), "trust": self.trust, "fps": 0,
            "det": 0, "feed": self.feed_health, "net": self.net_health,
        })

    def _update_trust(self):
        self.trust = round(
            100 * (W_FEED * self.feed_health
                   + W_NET * self.net_health
                   + W_CONTENT * self.content_health), 1)

    def _stamp(self, frame, integ):
        h = frame.shape[0]
        col = (0, 200, 60) if not integ["alerts"] else (60, 60, 255)
        cv2.rectangle(frame, (0, 0), (frame.shape[1] - 1, h - 1), col, 3)
        txt = self.name + ("  " + " ".join(integ["alerts"]) if integ["alerts"] else "")
        cv2.putText(frame, txt, (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    col, 2, cv2.LINE_AA)

    def snapshot(self):
        with self.lock:
            return self.jpeg

    def stop(self):
        self.running = False

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "source": self.source,
            "status": self.status, "fps": self.fps, "latency_ms": self.latency_ms,
            "net_ok": self.net_ok, "det_count": self.det_count,
            "det_labels": self.det_labels, "feed_health": round(self.feed_health, 3),
            "net_health": round(self.net_health, 3),
            "content_health": round(self.content_health, 3),
            "trust": self.trust, "alerts": sorted(set(self.alerts)),
            "history": list(self.history),
        }


class CameraManager:
    def __init__(self, detector):
        self.detector = detector
        self.cameras = {}
        self._lock = threading.Lock()
        self._next = 1
        self._load()

    def _load(self):
        if os.path.exists(STORE):
            try:
                for c in json.load(open(STORE)):
                    self.add(c["name"], c["source"], persist=False)
            except Exception as exc:  # noqa: BLE001
                print(f"[manager] could not load saved cameras: {exc}")

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(STORE, "w") as f:
            json.dump([{"name": c.name, "source": c.source}
                       for c in self.cameras.values()], f, indent=2)

    def add(self, name, source, persist=True):
        with self._lock:
            cam_id = f"cam{self._next}"
            self._next += 1
            self.cameras[cam_id] = Camera(cam_id, name or cam_id, source.strip(), self.detector)
            if persist:
                self._save()
            return cam_id

    def remove(self, cam_id):
        with self._lock:
            cam = self.cameras.pop(cam_id, None)
            if cam:
                cam.stop()
                self._save()
                return True
            return False

    def get(self, cam_id):
        return self.cameras.get(cam_id)

    def all(self):
        return [c.to_dict() for c in self.cameras.values()]

    def summary(self):
        cams = list(self.cameras.values())
        online = sum(1 for c in cams if c.status == "online")
        alerts = sum(1 for c in cams if c.alerts)
        avg_trust = round(sum(c.trust for c in cams) / len(cams), 1) if cams else 0
        total_det = sum(c.det_count for c in cams)
        return {
            "total": len(cams), "online": online, "offline": len(cams) - online,
            "alerts": alerts, "avg_trust": avg_trust, "detections": total_det,
            "detection_engine": "ON" if self.detector.available else "OFF",
        }
