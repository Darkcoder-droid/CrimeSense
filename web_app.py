"""
CrimeSense Web Application
Flask-based web dashboard for criminal detection system
Features:
  - Web dashboard with real-time alert feed
  - Criminal registration (upload images)
  - Image surveillance
  - Video surveillance
  - IoT integration with mock API
"""

import os
import cv2
import json
import time
import uuid
import base64
import shutil
import requests
import threading
import numpy
from datetime import datetime
from io import BytesIO
from functools import wraps

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename

from facerec import train_model, detect_faces, recognize_face

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SECRET_KEY'] = 'YOUR_SECRET_KEY_HERE'

ALERT_API_URL = "http://localhost:8080/api/alerts"
CAMERA_INPUT_DIR = "camera_input"
FACE_SAMPLES_DIR = "face_samples"
WATCHLIST_FILE = "Criminal.csv"

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(CAMERA_INPUT_DIR, exist_ok=True)
os.makedirs("profile_pics", exist_ok=True)

# In-memory alert store (mirrors flask_app alerts for web display)
alerts_received = []
model = None
names = None


def initialize_model():
    global model, names
    try:
        model, names = train_model()
        print(f"[CrimeSense] Model loaded: {len(names)} identities")
    except Exception as e:
        print(f"[CrimeSense] Warning: Could not load model: {e}")
        model = None
        names = {}


def publish_alert(detections, source="CrimeSense-Web"):
    """Publish detection alert to mock API server"""
    alert_payload = {
        "timestamp": datetime.now().isoformat(),
        "event_type": "criminal_detection",
        "source": source,
        "detections": detections,
        "confidence_threshold": 95
    }

    try:
        response = requests.post(
            ALERT_API_URL,
            json=alert_payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        if response.status_code in (200, 201, 202):
            print(f"[CrimeSense] Alert published: {len(detections)} detections")
            return True
    except requests.exceptions.ConnectionError:
        print("[CrimeSense] Could not connect to alert API (mock server not running)")
    except Exception as e:
        print(f"[CrimeSense] Alert publish error: {e}")

    return False


def is_watched(name):
    """Check if person is in watchlist"""
    if not os.path.exists(WATCHLIST_FILE):
        return False

    try:
        import csv
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Name', '').strip().lower() == name.strip().lower():
                    return True
    except Exception as e:
        print(f"[CrimeSense] Watchlist check error: {e}")

    return False


def process_image_for_detection(frame):
    """Process image frame and return detections"""
    global model, names

    if model is None:
        initialize_model()

    if model is None:
        return []

    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    face_coords = detect_faces(gray_frame)

    if len(face_coords) == 0:
        return [], frame

    frame_processed, recognized = recognize_face(model, frame, gray_frame, face_coords, names)

    detections = []
    for name, confidence in recognized:
        detections.append({
            "name": name,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })

    return detections, frame_processed


def allowed_file(filename, allowed_extensions={'png', 'jpg', 'jpeg', 'gif', 'pgm'}):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


# Initialize model on startup
initialize_model()


# ==================== ROUTES ====================

@app.route('/')
def index():
    """Home page with dashboard"""
    return render_template('dashboard.html', alerts=alerts_received)


@app.route('/dashboard')
def dashboard():
    """Dashboard with real-time alerts"""
    return render_template('dashboard.html', alerts=alerts_received)


@app.route('/api/alerts/history')
def get_alerts():
    """Get all alerts received"""
    return jsonify({"alerts": alerts_received, "count": len(alerts_received)})


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "alerts_received": len(alerts_received),
        "model_loaded": model is not None,
        "identities": len(names) if names else 0
    })


# ==================== CRIMINAL REGISTRATION ====================

@app.route('/register')
def register_page():
    """Criminal registration page"""
    return render_template('register.html')


@app.route('/api/register/criminal', methods=['POST'])
def register_criminal():
    """Register a new criminal with images"""
    try:
        name = request.form.get('name', '').strip()
        father_name = request.form.get('father_name', '').strip()
        gender = request.form.get('gender', '').strip()
        dob = request.form.get('dob', '').strip()
        crimes = request.form.get('crimes', '').strip()

        if not name:
            return jsonify({"status": "error", "message": "Name is required"}), 400

        # Get uploaded images
        files = request.files.getlist('images')
        if len(files) < 5:
            return jsonify({"status": "error", "message": "At least 5 images are required"}), 400

        # Check for valid images
        valid_images = []
        for f in files:
            if f and allowed_file(f.filename):
                valid_images.append(f)

        if len(valid_images) < 5:
            return jsonify({"status": "error", "message": "At least 5 valid images are required"}), 400

        # Create directory for criminal
        criminal_dir = os.path.join(FACE_SAMPLES_DIR, name.lower().replace(' ', '_'))
        if os.path.exists(criminal_dir):
            shutil.rmtree(criminal_dir, ignore_errors=True)
        os.makedirs(criminal_dir, exist_ok=True)

        # Process and save images
        from register import registerCriminal
        success_count = 0
        for i, file in enumerate(valid_images[:10], 1):  # Max 10 images
            # Read image
            in_memory_file = BytesIO(file.read())
            frame = cv2.imdecode(
                numpy.frombuffer(in_memory_file.getbuffer(), numpy.uint8),
                cv2.IMREAD_COLOR
            )

            if frame is not None:
                # Save temporary image
                temp_path = os.path.join(criminal_dir, f'temp_{i}.png')
                cv2.imwrite(temp_path, frame)

                # Process face detection
                result = registerCriminal(frame, criminal_dir, i)
                if result is None:
                    success_count += 1

                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        if success_count < 5:
            shutil.rmtree(criminal_dir, ignore_errors=True)
            return jsonify({
                "status": "error",
                "message": f"Need at least 5 images with detectable faces. Found: {success_count}"
            }), 400

        # Update watchlist CSV
        import csv
        file_exists = os.path.exists(WATCHLIST_FILE)
        with open(WATCHLIST_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['Name', "Father's Name", 'Gender', 'DOB', 'Crimes Done'])
            writer.writerow([name, father_name, gender, dob, crimes])

        # Save profile picture
        profile_img_num = int(request.form.get('profile_image', '1').split(' ')[1]) - 1
        if 0 <= profile_img_num < len(valid_images):
            profile_path = os.path.join("profile_pics", f"criminal_{name.lower().replace(' ', '_')}.png")
            in_memory_file = BytesIO(valid_images[profile_img_num].read())
            frame = cv2.imdecode(
                numpy.frombuffer(in_memory_file.getbuffer(), numpy.uint8),
                cv2.IMREAD_COLOR
            )
            if frame is not None:
                cv2.imwrite(profile_img_num, frame)

        # Reload model to include new criminal
        initialize_model()

        return jsonify({
            "status": "success",
            "message": f"Criminal '{name}' registered successfully with {success_count} images"
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==================== IMAGE SURVEILLANCE ====================

@app.route('/surveillance/image')
def image_surveillance():
    """Image surveillance page"""
    return render_template('surveillance_image.html')


@app.route('/api/surveillance/image', methods=['POST'])
def process_image():
    """Process uploaded image for criminal detection"""
    try:
        if 'image' not in request.files:
            return jsonify({"status": "error", "message": "No image provided"}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({"status": "error", "message": "No image selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({"status": "error", "message": "Invalid file type"}), 400

        # Read image
        frame = cv2.imdecode(
            numpy.frombuffer(file.read(), numpy.uint8),
            cv2.IMREAD_COLOR
        )

        if frame is None:
            return jsonify({"status": "error", "message": "Could not read image"}), 400

        # Process image
        detections, processed_frame = process_image_for_detection(frame)

        # Save processed image for display
        image_id = str(uuid.uuid4())
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{image_id}_processed.png')
        cv2.imwrite(image_path, processed_frame)

        # Publish alert if criminals detected
        watched_detections = [d for d in detections if is_watched(d['name'])]
        if watched_detections:
            publish_alert(watched_detections, source="CrimeSense-ImageSurveillance")
            # Store in alerts
            alerts_received.append({
                "received_at": datetime.now().isoformat(),
                "data": {
                    "timestamp": datetime.now().isoformat(),
                    "event_type": "criminal_detection",
                    "source": "CrimeSense-ImageSurveillance",
                    "detections": watched_detections,
                    "image_id": image_id
                }
            })

        return jsonify({
            "status": "success",
            "detections": detections,
            "image_id": image_id,
            "watched_count": len(watched_detections)
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded images"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ==================== VIDEO SURVEILLANCE ====================

@app.route('/surveillance/video')
def video_surveillance():
    """Video surveillance page"""
    return render_template('surveillance_video.html')


@app.route('/api/surveillance/video', methods=['POST'])
def process_video():
    """Process uploaded video for criminal detection"""
    try:
        if 'video' not in request.files:
            return jsonify({"status": "error", "message": "No video provided"}), 400

        file = request.files['video']
        if file.filename == '':
            return jsonify({"status": "error", "message": "No video selected"}), 400

        ext = file.filename.rsplit('.', 1)[1].lower()
        if ext not in ['mp4', 'mkv', 'avi', 'mov']:
            return jsonify({"status": "error", "message": "Invalid video format"}), 400

        # Save video
        video_id = str(uuid.uuid4())
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{video_id}.{ext}')
        file.save(video_path)

        # Process video in background
        def process_video_async():
            cap = cv2.VideoCapture(video_path)
            frame_count = 0
            all_detections = []
            max_frames = 300  # Process first 300 frames

            while cap.isOpened() and frame_count < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break

                detections, _ = process_image_for_detection(frame)
                watched_detections = [d for d in detections if is_watched(d['name'])]
                all_detections.extend(watched_detections)
                frame_count += 1

            cap.release()

            # Publish consolidated alert
            if all_detections:
                publish_alert(all_detections, source="CrimeSense-VideoSurveillance")
                alerts_received.append({
                    "received_at": datetime.now().isoformat(),
                    "data": {
                        "timestamp": datetime.now().isoformat(),
                        "event_type": "criminal_detection",
                        "source": "CrimeSense-VideoSurveillance",
                        "detections": all_detections,
                        "video_id": video_id,
                        "frames_processed": frame_count
                    }
                })

            # Clean up video file
            if os.path.exists(video_path):
                os.remove(video_path)

        thread = threading.Thread(target=process_video_async)
        thread.start()

        return jsonify({
            "status": "processing",
            "video_id": video_id,
            "message": "Video processing started in background"
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==================== CAMERA/SMART DETECTION ====================

@app.route('/camera')
def camera_page():
    """Live camera monitoring page"""
    return render_template('camera.html')


@app.route('/api/camera/detect', methods=['POST'])
def camera_detect():
    """Process camera frame from IoT device"""
    try:
        if 'frame' not in request.files:
            return jsonify({"status": "error", "message": "No frame provided"}), 400

        file = request.files['frame']
        frame = cv2.imdecode(
            numpy.frombuffer(file.read(), numpy.uint8),
            cv2.IMREAD_COLOR
        )

        if frame is None:
            return jsonify({"status": "error", "message": "Could not read frame"}), 400

        detections, _ = process_image_for_detection(frame)
        watched_detections = [d for d in detections if is_watched(d['name'])]

        if watched_detections:
            publish_alert(watched_detections, source="CrimeSense-Camera")
            alerts_received.append({
                "received_at": datetime.now().isoformat(),
                "data": {
                    "timestamp": datetime.now().isoformat(),
                    "event_type": "criminal_detection",
                    "source": "CrimeSense-Camera",
                    "detections": watched_detections
                }
            })

        return jsonify({
            "status": "success",
            "detections": watched_detections
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==================== CRIMINALS LIST ====================

@app.route('/criminals')
def criminals_list():
    """View all registered criminals"""
    criminals = []
    try:
        import csv
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get('Name', '').strip()
                    if name:
                        profile_path = f"profile_pics/criminal_{name.lower().replace(' ', '_')}.png"
                        criminals.append({
                            "name": name,
                            "father_name": row.get("Father's Name", ''),
                            "gender": row.get('Gender', ''),
                            "dob": row.get('DOB', ''),
                            "crimes": row.get('Crimes Done', ''),
                            "profile_pic": profile_path if os.path.exists(profile_path) else None
                        })
    except Exception as e:
        print(f"Error loading criminals: {e}")

    return render_template('criminals.html', criminals=criminals)


# ==================== ALERTS ====================

@app.route('/api/alerts/push', methods=['POST'])
def push_alert():
    """Endpoint for IoT devices to push alerts (also used by flask_app)"""
    data = request.json
    if data:
        alerts_received.append({
            "received_at": datetime.now().isoformat(),
            "data": data
        })
    return jsonify({"status": "received"})


if __name__ == '__main__':
    print("=" * 60)
    print("  CrimeSense Security Command Center")
    print("=" * 60)
    print(f"  Web Dashboard: http://localhost:5000")
    print(f"  Alert API:     http://localhost:5000/api/alerts/push")
    print(f"  Camera API:   http://localhost:5000/api/camera/detect")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)