#!/usr/bin/env python3
"""
CrimeSense IoT System - Quick Start Script
Usage:
    1. Start mock API server: python flask_app.py
    2. Start IoT hub: python start_iot.py
    3. Place test images in /camera_input
"""

import os
import sys
import time
import json
import cv2

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from iot_hub import IoTHub, CAMERA_INPUT_DIR

def test_camera_watcher():
    """Test the camera watchdog with sample images"""
    print("\n=== Testing Camera Watchdog ===")

    # Create test images directory
    test_dir = CAMERA_INPUT_DIR
    if not os.path.exists(test_dir):
        os.makedirs(test_dir, exist_ok=True)
        print(f"Created: {test_dir}")

    # Copy a sample from face_samples if available
    sample_dir = "face_samples"
    if os.path.exists(sample_dir):
        for subdir in os.listdir(sample_dir):
            subpath = os.path.join(sample_dir, subdir)
            if os.path.isdir(subpath):
                sample_file = None
                for f in os.listdir(subpath):
                    if f.endswith(('.jpg', '.png', '.jpeg')):
                        sample_file = os.path.join(subpath, f)
                        break

                if sample_file:
                    test_image = os.path.join(test_dir, f"test_{subdir}.jpg")
                    if not os.path.exists(test_image):
                        import shutil
                        shutil.copy(sample_file, test_image)
                        print(f"Copied test image: {test_image}")
                    break

    print("Camera watchdog test complete")


def test_model():
    """Test face recognition model"""
    print("\n=== Testing Face Recognition Model ===")

    from facerec import train_model, detect_faces, recognize_face
    model, names = train_model()

    if not names:
        print("No faces trained. Add criminals first!")
        return None, None

    print(f"Model loaded: {len(names)} identities")
    print(f"Known criminals: {list(names.values())}")
    return model, names


def test_iot_alerts():
    """Test JSON POST functionality"""
    print("\n=== Testing JSON Alert Publishing ===")

    from iot_hub import AlertPublisher
    publisher = AlertPublisher("http://localhost:8080/api/alerts")

    # Test alert
    test_detection = [{
        "name": "Test Criminal",
        "confidence": 85,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
    }]

    result = publisher.publish(test_detection)
    print(f"Alert test result: {'SUCCESS' if result else 'FAILED (API not running)'}")
    print(f"Alert history: {len(publisher.alert_history)} alerts logged")

    return publisher


def interactive_mode():
    """Run IoT Hub in interactive mode"""
    print("\n=== CrimeSense IoT Hub - Interactive Mode ===")
    print("Starting IoT services...")

    # Initialize and start IoT Hub
    hub = IoTHub()
    camera_thread, watchlist_thread = hub.start()

    print("\nServices started:")
    print(f"  - Camera Watchdog: monitoring {CAMERA_INPUT_DIR}")
    print(f"  - Watchlist Sync: syncing Criminal.csv")
    print(f"  - Alert Publisher: posting to http://localhost:8080/api/alerts")
    print("\nTo test:")
    print("  1. Start mock server: python flask_app.py")
    print("  2. Add images/videos to /camera_input")
    print("  3. Check /api/alerts/history for alerts")
    print("\nPress Ctrl+C to stop\n")

    try:
        while True:
            time.sleep(5)
            status = hub.get_status()
            print(f"[Status Update]")
            print(f"  Criminals in watchlist: {status['watchlist_sync']['criminals_count']}")
            print(f"  Alerts published: {status['alert_publisher']['alerts_sent']}")
            print(f"  Model loaded: {status['model']['loaded']}")
            print(f"  Model identities: {status['model']['identities']}")
    except KeyboardInterrupt:
        print("\n\nShutting down IoT Hub...")
        hub.stop()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CrimeSense IoT Hub")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    parser.add_argument("--server", action="store_true", help="Start mock API server")

    args = parser.parse_args()

    if args.server:
        from flask_app import run_server
        run_server()
        return

    if args.test:
        test_camera_watcher()
        test_model()
        test_iot_alerts()
        print("\n=== All Tests Complete ===")
    elif args.interactive:
        interactive_mode()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()