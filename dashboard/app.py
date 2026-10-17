"""
app.py - Secure Camera Network : analytics dashboard (Flask, no Streamlit)

Run:
    python -m venv venv
    venv\\Scripts\\activate            (Windows)   |   source venv/bin/activate (Linux)
    pip install -r requirements.txt
    python app.py

Then open http://localhost:8501

Add a camera from the dashboard by pasting its stream link, e.g.
    http://pi.local:8080/video
    http://pi1.local:8080/video
or add the laptop webcam with source  webcam:0
"""

import time

from flask import Flask, Response, jsonify, render_template, request

from detector import Detector
from camera_manager import CameraManager

PORT = 8501

app = Flask(__name__)
detector = Detector(model_path="yolov8n.pt", confidence=0.45)
manager = CameraManager(detector)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/cameras", methods=["GET"])
def list_cameras():
    return jsonify({"cameras": manager.all(), "summary": manager.summary()})


@app.route("/api/cameras", methods=["POST"])
def add_camera():
    data = request.get_json(force=True, silent=True) or {}
    source = (data.get("source") or "").strip()
    name = (data.get("name") or "").strip()
    if not source:
        return jsonify({"error": "source (stream link or webcam:0) is required"}), 400
    # friendly: allow pasting the Pi test page without /video
    if source.startswith("http") and not source.rstrip("/").endswith(
            ("/video", ".jpg", ".mjpg", ".mjpeg")):
        source = source.rstrip("/") + "/video"
    cam_id = manager.add(name or source, source)
    return jsonify({"id": cam_id})


@app.route("/api/cameras/<cam_id>", methods=["DELETE"])
def delete_camera(cam_id):
    return jsonify({"ok": manager.remove(cam_id)})


@app.route("/camera/<cam_id>/video")
def camera_video(cam_id):
    cam = manager.get(cam_id)
    if not cam:
        return "no such camera", 404

    def gen():
        last = None
        while True:
            frame = cam.snapshot()
            if frame is None or frame is last:
                time.sleep(0.03)
                continue
            last = frame
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    print("=" * 60)
    print("  Secure Camera Network - Dashboard")
    print(f"  Open  http://localhost:{PORT}")
    print(f"  Detection engine: {'ON' if detector.available else 'OFF (yolov8n.pt missing)'}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=PORT, threaded=True)
