"""
IoT-Enabled Video Surveillance
Replaces CSV logging with JSON POST requests to the mock API
Uses existing recognize_face as the core detection function
"""

import time
import json
import requests
from datetime import datetime

ALERT_API_URL = "http://localhost:8080/api/alerts"


def create_iot_video_loop(recognize_func, detect_faces_func):
    """
    Factory function that creates an IoT-enabled video loop
    Uses the existing recognize_face function as the core
    """

    def iot_video_loop(path, model, names):
        """
        IoT-enabled video processing loop
        Replaces CSV logging with JSON POST requests
        """
        import cv2

        p = path
        q = __import__('ntpath').basename(p)
        filenam, file_extension = __import__('os').path.splitext(q)

        from home import thread_event, left_frame, webcam, right_frame
        start = time.time()
        webcam = cv2.VideoCapture(p)

        # Get the alert publisher from IoT Hub
        from iot_hub import AlertPublisher
        alert_publisher = AlertPublisher(ALERT_API_URL)

        old_recognized = []
        crims_found_labels = []
        img_label = None

        # Track detections for batch posting
        detection_buffer = []
        last_post_time = time.time()
        POST_INTERVAL = 5  # Post alerts every 5 seconds

        try:
            while not thread_event.is_set():
                # Read frame from video
                while True:
                    (return_val, frame) = webcam.read()
                    if return_val == True:
                        break

                # Flip and convert to grayscale
                frame = cv2.flip(frame, 1, 0)
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # Detect and recognize using core function
                face_coords = detect_faces_func(gray_frame)
                (frame, recognized) = recognize_func(model, frame, gray_frame, face_coords, names)

                # Process recognized faces
                recog_names = [item[0] for item in recognized]
                if recog_names != old_recognized:
                    for wid in right_frame.winfo_children():
                        wid.destroy()
                    crims_found_labels.clear()

                    for i, crim in enumerate(recognized):
                        crims_found_labels.append(__import__('tkinter').Label(
                            right_frame, text=crim[0], bg="orange",
                            font="Arial 15 bold", pady=20))
                        crims_found_labels[i].pack(fill="x", padx=20, pady=10)

                        # Log to buffer instead of CSV
                        detection = {
                            "name": crim[0],
                            "timestamp": datetime.now().isoformat(),
                            "elapsed_seconds": time.time() - start
                        }
                        detection_buffer.append(detection)

                        print(f"[IoT] Detected: {crim[0]} at {detection['elapsed_seconds']:.2f}s")

                    old_recognized = recog_names

                # Periodic JSON POST
                current_time = time.time()
                if detection_buffer and (current_time - last_post_time) >= POST_INTERVAL:
                    alert_payload = {
                        "timestamp": datetime.now().isoformat(),
                        "event_type": "criminal_detection",
                        "source": "CrimeSense-VideoSurveillance",
                        "video_file": filenam + file_extension,
                        "detections": detection_buffer
                    }

                    try:
                        response = requests.post(
                            ALERT_API_URL,
                            json=alert_payload,
                            headers={"Content-Type": "application/json"},
                            timeout=3
                        )
                        if response.status_code in (200, 201, 202):
                            print(f"[IoT] Alert posted: {len(detection_buffer)} detections")
                    except Exception as e:
                        print(f"[IoT] POST failed: {e}")

                    detection_buffer.clear()
                    last_post_time = current_time

                # Display video stream
                from home import showImage
                img_size = min(left_frame.winfo_width(), left_frame.winfo_height()) - 20
                showImage(frame, img_size)

        except RuntimeError:
            print("[IoT] Caught Runtime Error")
        except __import__('tkinter').TclError:
            print("[IoT] Caught Tcl Error")
        finally:
            # Final POST for remaining detections
            if detection_buffer:
                alert_payload = {
                    "timestamp": datetime.now().isoformat(),
                    "event_type": "video_session_ended",
                    "source": "CrimeSense-VideoSurveillance",
                    "video_file": filenam + file_extension,
                    "detections": detection_buffer
                }
                try:
                    requests.post(ALERT_API_URL, json=alert_payload, timeout=3)
                except:
                    pass

    return iot_video_loop


def post_detection_alert(name, confidence, source="CrimeSense"):
    """
    Simple function to post a single detection alert
    Can be called from anywhere in the application
    """
    alert_payload = {
        "timestamp": datetime.now().isoformat(),
        "event_type": "criminal_detection",
        "source": source,
        "detections": [{
            "name": name,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }]
    }

    try:
        response = requests.post(
            ALERT_API_URL,
            json=alert_payload,
            headers={"Content-Type": "application/json"},
            timeout=3
        )
        return response.status_code in (200, 201, 202)
    except:
        return False