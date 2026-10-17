
# 📷 Secure Camera Network
### Raspberry Pi Live Camera Streaming Server

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-green?logo=opencv)
![Flask](https://img.shields.io/badge/Flask-Web%20Server-black?logo=flask)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-red)
![Streaming](https://img.shields.io/badge/Streaming-MJPEG-orange)

## 📌 Overview

Secure Camera Network is a Python-based camera streaming server designed to run on a Raspberry Pi connected to a USB webcam.

It captures camera frames using OpenCV, encodes them as JPEG images, and streams them over a local network using Flask. Other devices, such as laptops and web dashboards, can access the live video through an HTTP URL.

The server also provides snapshot capture, health monitoring, configurable camera settings, and optional access-key authentication.

Object detection can be performed by a separate laptop or server that consumes the video stream.

## 🎯 Project Objectives

- Stream live camera video over a local network.
- Provide browser-based camera monitoring.
- Support USB webcams and video-file sources.
- Monitor camera status and streaming performance.
- Automatically reconnect when a camera becomes unavailable.
- Provide a JPEG snapshot endpoint.
- Support optional access-key authentication.
- Enable integration with external computer vision applications.

## ✨ Features

### 📹 1. Live Video Streaming
- MJPEG video streaming over HTTP.
- Browser-compatible video endpoint.
- Configurable resolution and frame rate.
- JPEG image quality configuration.
- Shared camera capture thread for multiple viewers.

### 📸 2. Snapshot Capture
- Capture the latest available JPEG frame.
- Access snapshots through an HTTP endpoint.
- Return an HTTP error when no frame is available.

### 💓 3. Health Monitoring
The health endpoint returns JSON information including:

- Camera node ID.
- Hostname.
- Camera availability.
- Video source.
- Resolution.
- Measured FPS.
- Total captured frames.
- Last frame age.
- Server uptime.
- Camera error information.
- Whether access-key authentication is enabled.

### 🔄 4. Automatic Camera Recovery
- Detect camera initialization failures.
- Retry opening an unavailable camera.
- Attempt reconnection after frame-read failures.
- Support video-file playback in a continuous loop.

### 🔐 5. Optional Authentication
An optional access key can protect the HTTP endpoints.

Clients must supply the configured key through the `key` query parameter.

**Security note:** Query-string keys can appear in logs and browser history. Use this mechanism only in trusted environments, and consider stronger authentication and HTTPS for production deployments.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic |
| OpenCV | Camera capture and JPEG encoding |
| Flask | HTTP server and API endpoints |
| Threading | Background camera capture |
| MJPEG | Live video streaming |
| JSON | Health status responses |
| Raspberry Pi | Camera streaming node |
| USB Webcam | Video input |

## 🏗️ System Architecture

```text
             USB Webcam / Video File
                       |
                       v
                OpenCV Capture
                       |
                       v
               Camera Background
                    Thread
                       |
                       v
                JPEG Encoding
                       |
                       v
              Flask HTTP Server
                       |
          +------------+------------+
          |            |            |
          v            v            v
      /video     /snapshot.jpg   /health
          |            |            |
          v            v            v
     Live MJPEG     JPEG Image   JSON Status
          |
          v
    Laptop / Dashboard
          |
          v
 Optional YOLO Detection
```

## 📂 Project Structure

```text
secure-camera-network/
│
├── pi_camera_server.py
├── requirements.txt
├── README.md
└── .gitignore
```

This structure describes the camera server component. Add other files and directories as your project grows.

## ⚙️ Requirements

- Raspberry Pi or another compatible Linux computer.
- Python 3.9 or newer.
- USB webcam, or a supported video file for testing.
- Network connectivity between the camera node and client.
- OpenCV and Flask.

## 🚀 Installation

### Step 1: Clone the Repository

Replace the example URL with your actual GitHub repository URL.

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd YOUR_PROJECT_FOLDER
```

Alternatively, download the project and open its directory.

### Step 2: Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows, activate the environment using:

```powershell
.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

Create a `requirements.txt` file containing:

```text
Flask
opencv-python
```

Then run:

```bash
pip install -r requirements.txt
```

On a Raspberry Pi without a graphical desktop, a compatible headless OpenCV package may be preferable. Install only one OpenCV package in the environment.

### Step 4: Connect the Camera

Connect a USB webcam to the Raspberry Pi.

Check available video devices on Linux:

```bash
ls /dev/video*
```

Make sure the application has permission to access the selected camera.

## ▶️ Usage

### 1. Start the Server

Use the default camera and port:

```bash
python3 pi_camera_server.py
```

The default configuration is:

- Camera index: `0`
- Port: `8080`
- Resolution: `640 × 480`
- Target frame rate: `15 FPS`
- JPEG quality: `70`

### 2. Configure the Camera

```bash
python3 pi_camera_server.py \
  --camera 0 \
  --port 8080 \
  --width 640 \
  --height 480 \
  --fps 15 \
  --quality 70 \
  --node-id pi-camera-01
```

### 3. Stream a Video File

Use a video file instead of a physical camera:

```bash
python3 pi_camera_server.py --camera test.mp4
```

When the video reaches the end, the application attempts to restart playback from the beginning.

### 4. Enable Access-Key Authentication

```bash
python3 pi_camera_server.py --key YOUR_SECRET_KEY
```

Use a strong, private key. Avoid publishing it in source code, screenshots, or public URLs.

## 🌐 HTTP Endpoints

Assuming the server is running on port `8080`:

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Browser-based camera test page |
| `/video` | GET | Continuous MJPEG video stream |
| `/snapshot.jpg` | GET | Latest JPEG frame |
| `/health` | GET | JSON camera and server status |

Example local URLs:

```text
http://localhost:8080/
http://localhost:8080/video
http://localhost:8080/snapshot.jpg
http://localhost:8080/health
```

For access from another device, replace `localhost` with the Raspberry Pi's hostname or LAN IP address.

With authentication enabled, append the configured key:

```text
http://localhost:8080/video?key=YOUR_SECRET_KEY
```

The same key requirement applies to the other endpoints.

## ⚙️ Configuration Options

| Argument | Default | Description |
|---|---|---|
| `--camera` | `0` | Camera index or video-file path |
| `--port` | `8080` | HTTP server port |
| `--width` | `640` | Output frame width |
| `--height` | `480` | Output frame height |
| `--fps` | `15` | Target capture frame rate |
| `--quality` | `70` | JPEG encoding quality |
| `--node-id` | Hostname | Camera node identifier |
| `--key` | Empty | Optional access key |

The script also supports environment variables:

| Environment Variable | Purpose |
|---|---|
| `CAMERA_INDEX` | Camera source |
| `STREAM_PORT` | Server port |
| `CAMERA_WIDTH` | Frame width |
| `CAMERA_HEIGHT` | Frame height |
| `CAMERA_FPS` | Target FPS |
| `JPEG_QUALITY` | JPEG quality |
| `CAMERA_NODE_ID` | Camera node identifier |
| `STREAM_KEY` | Optional access key |

Command-line arguments override the corresponding environment-variable defaults.

## 📊 Health Monitoring Example

The `/health` endpoint returns JSON similar to this:

```json
{
  "node_id": "pi-camera-01",
  "hostname": "raspberrypi",
  "camera_ok": true,
  "source": "0",
  "resolution": "640x480",
  "fps": 14.8,
  "frames_sent": 1200,
  "last_frame_age_s": 0.1,
  "uptime_s": 300,
  "error": "",
  "auth": false
}
```

The values above are illustrative, not measured results.

## 🔗 Integration With AI Applications

The MJPEG stream can be consumed by a separate computer vision application.

Possible integrations include:

- YOLO object detection.
- People and vehicle detection.
- Multi-camera monitoring.
- Real-time video analytics.
- Custom computer vision dashboards.
- Remote camera health monitoring.

The uploaded `pi_camera_server.py` file provides the streaming infrastructure. It does not itself implement YOLO inference, object tracking, or detection-result visualization.

## 🔒 Security Considerations

- Keep the camera server on a trusted network.
- Do not expose the development server directly to the public internet.
- Use HTTPS and stronger authentication for production.
- Avoid embedding secrets in URLs or source code.
- Restrict network access through firewall rules.
- Keep Python dependencies updated.
- Consider a production WSGI server and reverse proxy for deployment.

## 🧰 Troubleshooting

### Camera cannot open

- Verify the USB connection.
- Check the camera index.
- Check Linux device permissions.
- Close other applications using the webcam.
- Verify that OpenCV supports the selected camera backend.

### Stream is unavailable

- Confirm that the server is running.
- Verify the hostname, IP address, and port.
- Check local network connectivity.
- Inspect terminal logs for camera errors.

### Access returns HTTP 401

If access-key authentication is enabled, provide the correct `key` query parameter.

### Snapshot returns HTTP 503

The camera has not yet supplied an available JPEG frame. Check camera initialization and server logs.

### Low frame rate

Try lowering the resolution, target FPS, or JPEG quality. Actual performance depends on the camera, hardware, and network.

## 🔮 Future Enhancements

- Secure token-based authentication.
- HTTPS support.
- Camera configuration through a web interface.
- Multi-camera management.
- Structured logging and improved metrics.
- Docker deployment.
- Automated tests and CI/CD.
- YOLO inference on a separate computer.
- Object detection event notifications.
- Camera availability monitoring.

These are proposed improvements, not features confirmed in the current source file.

## 👨‍💻 Author

**GitHub:** [@oviya0810](https://github.com/oviya0810)

## 📄 License

Choose and include an appropriate license file before distributing this project. Do not claim a specific license until it has been added to the repository.

---

⭐ If you find this project useful, consider starring the repository!
