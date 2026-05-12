"""
IoT Hub for CrimeSense - Real-time Criminal Detection System
Features:
  1. Camera Watchdog - monitors /camera_input for new frames
  2. Real-time Watchlist Sync - keeps criminal database synchronized
  3. JSON Alert Publisher - posts detection alerts to remote API
"""

import os
import json
import time
import threading
import hashlib
import requests
from datetime import datetime
from facerec import train_model, detect_faces, recognize_face

# Configuration
CAMERA_INPUT_DIR = "camera_input"
WATCHLIST_FILE = "Criminal.csv"
ALERT_API_URL = "http://localhost:8080/api/alerts"  # Mock API endpoint
SYNC_INTERVAL = 5  # seconds
WATCHDOG_INTERVAL = 1  # seconds


class CameraWatcher:
    """Watchdog that monitors /camera_input for new camera frames/images"""

    def __init__(self, input_dir=CAMERA_INPUT_DIR):
        self.input_dir = input_dir
        self.processed_files = set()
        self.callback = None
        self.running = False
        self._init_directory()

    def _init_directory(self):
        """Initialize camera input directory if it doesn't exist"""
        if not os.path.exists(self.input_dir):
            os.makedirs(self.input_dir, exist_ok=True)
            print(f"[CameraWatcher] Created directory: {self.input_dir}")

    def register_callback(self, callback):
        """Register callback function to handle new files"""
        self.callback = callback

    def _get_file_hash(self, filepath):
        """Generate hash for file to track processed files"""
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def scan(self):
        """Scan for new files in camera input directory"""
        new_files = []
        if not os.path.exists(self.input_dir):
            return new_files

        for filename in os.listdir(self.input_dir):
            filepath = os.path.join(self.input_dir, filename)
            if not os.path.isfile(filepath):
                continue

            file_hash = self._get_file_hash(filepath)
            if file_hash not in self.processed_files:
                self.processed_files.add(file_hash)
                new_files.append((filepath, filename))

        return new_files

    def start(self):
        """Start the watchdog monitoring loop"""
        self.running = True
        print(f"[CameraWatcher] Started monitoring {self.input_dir}")

        def watchdog_loop():
            while self.running:
                new_files = self.scan()
                for filepath, filename in new_files:
                    print(f"[CameraWatcher] New file detected: {filename}")
                    if self.callback:
                        self.callback(filepath, filename)
                time.sleep(WATCHDOG_INTERVAL)

        thread = threading.Thread(target=watchdog_loop, daemon=True)
        thread.start()
        return thread

    def stop(self):
        """Stop the watchdog"""
        self.running = False
        print("[CameraWatcher] Stopped")


class WatchlistSync:
    """Real-time synchronization for criminal watchlist"""

    def __init__(self, watchlist_file=WATCHLIST_FILE):
        self.watchlist_file = watchlist_file
        self.criminals = {}
        self.last_sync = None
        self.callback = None
        self.running = False
        self._load_watchlist()

    def _load_watchlist(self):
        """Load watchlist from file"""
        self.criminals = {}
        if not os.path.exists(self.watchlist_file):
            print(f"[WatchlistSync] Watchlist file not found: {self.watchlist_file}")
            return

        try:
            import csv
            with open(self.watchlist_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get('Name', '').strip().lower()
                    if name:
                        self.criminals[name] = row
            print(f"[WatchlistSync] Loaded {len(self.criminals)} criminals from watchlist")
        except Exception as e:
            print(f"[WatchlistSync] Error loading watchlist: {e}")

    def sync(self):
        """Synchronize watchlist with file system"""
        old_count = len(self.criminals)
        self._load_watchlist()
        new_count = len(self.criminals)

        if old_count != new_count:
            print(f"[WatchlistSync] Watchlist updated: {old_count} -> {new_count} criminals")
            if self.callback:
                self.callback(self.criminals)

        self.last_sync = datetime.now()
        return self.criminals

    def get_criminals(self):
        """Get current watchlist"""
        return self.criminals

    def is_watched(self, name):
        """Check if a person is in the watchlist"""
        return name.strip().lower() in self.criminals

    def register_callback(self, callback):
        """Register callback for watchlist updates"""
        self.callback = callback

    def start(self):
        """Start periodic sync"""
        self.running = True
        print(f"[WatchlistSync] Started periodic sync (interval: {SYNC_INTERVAL}s)")

        def sync_loop():
            while self.running:
                self.sync()
                time.sleep(SYNC_INTERVAL)

        thread = threading.Thread(target=sync_loop, daemon=True)
        thread.start()
        return thread

    def stop(self):
        """Stop periodic sync"""
        self.running = False
        print("[WatchlistSync] Stopped")


class AlertPublisher:
    """Publishes detection alerts as JSON POST requests"""

    def __init__(self, api_url=ALERT_API_URL):
        self.api_url = api_url
        self.alert_history = []
        self.running = False

    def publish(self, detection_data):
        """Publish detection alert as JSON to API"""
        alert_payload = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "criminal_detection",
            "source": "CrimeSense-IoT",
            "detections": detection_data,
            "confidence_threshold": 95
        }

        try:
            response = requests.post(
                self.api_url,
                json=alert_payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )

            if response.status_code in (200, 201, 202):
                print(f"[AlertPublisher] Alert published successfully: {response.status_code}")
                self.alert_history.append({"status": "success", "payload": alert_payload})
                return True
            else:
                print(f"[AlertPublisher] API returned {response.status_code}: {response.text}")
                self.alert_history.append({"status": "failed", "code": response.status_code, "payload": alert_payload})
                return False

        except requests.exceptions.ConnectionError:
            print("[AlertPublisher] Could not connect to API (mock server not running)")
            self.alert_history.append({"status": "connection_error", "payload": alert_payload})
            return False
        except requests.exceptions.Timeout:
            print("[AlertPublisher] Request timed out")
            self.alert_history.append({"status": "timeout", "payload": alert_payload})
            return False
        except Exception as e:
            print(f"[AlertPublisher] Error: {e}")
            self.alert_history.append({"status": "error", "error": str(e), "payload": alert_payload})
            return False

    def get_history(self):
        """Get alert history"""
        return self.alert_history


class IoTHub:
    """Main IoT Hub that integrates all components"""

    def __init__(self, camera_input_dir=CAMERA_INPUT_DIR,
                 watchlist_file=WATCHLIST_FILE,
                 alert_api_url=ALERT_API_URL):

        self.camera_watcher = CameraWatcher(camera_input_dir)
        self.watchlist_sync = WatchlistSync(watchlist_file)
        self.alert_publisher = AlertPublisher(alert_api_url)
        self.model = None
        self.names = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the face recognition model"""
        print("[IoTHub] Loading face recognition model...")
        try:
            self.model, self.names = train_model()
            print(f"[IoTHub] Model loaded: {len(self.names)} identities")
        except Exception as e:
            print(f"[IoTHub] Warning: Could not load model: {e}")
            self.model = None
            self.names = {}

    def process_frame(self, frame):
        """Process a single frame using the core recognize_face function"""
        if self.model is None:
            print("[IoTHub] Model not initialized")
            return [], frame

        import cv2
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_coords = detect_faces(gray_frame)

        if len(face_coords) == 0:
            return [], frame

        frame, recognized = recognize_face(self.model, frame, gray_frame, face_coords, self.names)

        # Filter: only report if person is in watchlist
        detections = []
        for name, confidence in recognized:
            if self.watchlist_sync.is_watched(name):
                detections.append({
                    "name": name,
                    "confidence": confidence,
                    "timestamp": datetime.now().isoformat()
                })

        return detections, frame

    def process_file(self, filepath, filename):
        """Process an image or video file from camera input"""
        import cv2

        ext = os.path.splitext(filename)[1].lower()
        detections = []

        if ext in ['.jpg', '.jpeg', '.png', '.pgm']:
            # Process single image
            frame = cv2.imread(filepath)
            if frame is not None:
                detections, _ = self.process_frame(frame)

        elif ext in ['.mp4', '.mkv', '.avi']:
            # Process video frame by frame
            cap = cv2.VideoCapture(filepath)
            frame_count = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_dets, _ = self.process_frame(frame)
                detections.extend(frame_dets)
                frame_count += 1

                # Limit processing to 100 frames for demo
                if frame_count >= 100:
                    break
            cap.release()

        # Publish alert if detections found
        if detections:
            print(f"[IoTHub] Detected {len(detections)} criminals: {[d['name'] for d in detections]}")
            self.alert_publisher.publish(detections)

        return detections

    def handle_new_file(self, filepath, filename):
        """Callback for camera watcher"""
        print(f"[IoTHub] Processing: {filename}")
        return self.process_file(filepath, filename)

    def start(self):
        """Start all IoT components"""
        self.camera_watcher.register_callback(self.handle_new_file)
        self.watchlist_sync.register_callback(lambda x: print(f"[IoTHub] Watchlist updated: {len(x)} criminals"))

        camera_thread = self.camera_watcher.start()
        watchlist_thread = self.watchlist_sync.start()

        print("[IoTHub] All services started")
        return camera_thread, watchlist_thread

    def stop(self):
        """Stop all IoT components"""
        self.camera_watcher.stop()
        self.watchlist_sync.stop()
        print("[IoTHub] All services stopped")

    def get_status(self):
        """Get status of all components"""
        return {
            "camera_watcher": {
                "input_dir": self.camera_watcher.input_dir,
                "processed_files": len(self.camera_watcher.processed_files)
            },
            "watchlist_sync": {
                "watchlist_file": self.watchlist_sync.watchlist_file,
                "criminals_count": len(self.watchlist_sync.criminals),
                "last_sync": self.watchlist_sync.last_sync.isoformat() if self.watchlist_sync.last_sync else None
            },
            "alert_publisher": {
                "api_url": self.alert_publisher.api_url,
                "alerts_sent": len(self.alert_publisher.alert_history)
            },
            "model": {
                "loaded": self.model is not None,
                "identities": len(self.names)
            }
        }


def demo():
    """Demo function to test the IoT Hub"""
    hub = IoTHub()

    # Start IoT services
    camera_thread, watchlist_thread = hub.start()

    try:
        # Keep running
        print("\n[IoTHub] Demo running... Press Ctrl+C to stop")
        print("[IoTHub] Place images/videos in /camera_input to test")

        while True:
            time.sleep(10)
            status = hub.get_status()
            print(f"\n[Status] {json.dumps(status, indent=2)}")

    except KeyboardInterrupt:
        print("\n[IoTHub] Shutting down...")
        hub.stop()


if __name__ == "__main__":
    demo()