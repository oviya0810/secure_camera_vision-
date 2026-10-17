"""
detector.py - YOLOv8 object detection wrapper.

Runs on the laptop (not the Pi). Loads the model once and reuses it for every
camera. If ultralytics / the model file is missing, it degrades gracefully to
a "detection off" mode so the rest of the dashboard still runs.
"""

import threading

import cv2

# Colours (BGR) used for the detection boxes drawn on the frame.
_BOX_COLORS = [
    (80, 220, 255),   # yellow
    (0, 200, 60),     # green
    (255, 120, 0),    # blue
    (60, 60, 255),    # red
    (230, 80, 230),   # violet
    (0, 180, 255),    # orange
]


class Detector:
    def __init__(self, model_path="yolov8n.pt", confidence=0.45):
        self.confidence = confidence
        self.model = None
        self.available = False
        self.names = {}
        self._lock = threading.Lock()
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            self.names = self.model.names
            self.available = True
            print(f"[detector] YOLO loaded ({model_path})")
        except Exception as exc:  # noqa: BLE001
            print(f"[detector] YOLO not available, detection disabled: {exc}")

    def detect(self, frame):
        """Return (annotated_frame, detections list[dict]). detections carry
        label + confidence, used by the dashboard for counts / graphs."""
        if not self.available or frame is None:
            return frame, []

        try:
            with self._lock:
                results = self.model.predict(
                    frame, conf=self.confidence, verbose=False, imgsz=480
                )[0]
        except Exception as exc:  # noqa: BLE001
            print(f"[detector] predict failed: {exc}")
            return frame, []

        detections = []
        boxes = getattr(results, "boxes", None)
        if boxes is None:
            return frame, []

        for box in boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            label = self.names.get(cls, str(cls))
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
            color = _BOX_COLORS[cls % len(_BOX_COLORS)]
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            tag = f"{label} {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
            cv2.putText(frame, tag, (x1 + 3, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (15, 15, 15), 1, cv2.LINE_AA)
            detections.append({"label": label, "confidence": round(conf, 3)})

        return frame, detections
