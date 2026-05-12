"""
CrimeSense Startup Script
Runs both the web dashboard and IoT mock API server
"""

import subprocess
import sys
import time

print("=" * 60)
print("  CrimeSense Security System")
print("=" * 60)

# Start mock API server in background
print("\n[1/2] Starting Mock API Server (IoT Hub) on port 8080...")
api_process = subprocess.Popen(
    [sys.executable, "flask_app.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)

time.sleep(1)

# Start web app
print("[2/2] Starting Web Dashboard on port 5000...")
web_process = subprocess.Popen(
    [sys.executable, "web_app.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)

print("\n" + "=" * 60)
print("  CrimeSense is running!")
print("=" * 60)
print("  Web Dashboard: http://localhost:5000")
print("  IoT API:        http://localhost:8080")
print("  Dashboard:      http://localhost:8080/dashboard")
print("=" * 60)
print("\nPress Ctrl+C to stop all services\n")

try:
    # Monitor both processes
    while True:
        if api_process.poll() is not None:
            print("[ERROR] IoT API server stopped unexpectedly")
            break
        if web_process.poll() is not None:
            print("[ERROR] Web server stopped unexpectedly")
            break
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\nStopping CrimeSense services...")
    api_process.terminate()
    web_process.terminate()
    print("All services stopped.")