# CrimeSense - AI-Powered Criminal Detection System

A comprehensive security system combining facial recognition, IoT integration, and real-time monitoring for criminal detection.

## Project Overview

CrimeSense is a multi-platform security solution that:
- Detects criminals using face recognition (LBPH algorithm)
- Integrates with IoT devices for real-time surveillance
- Provides a web dashboard for monitoring alerts
- Supports image/video surveillance
- Sends alerts via Firebase and Gmail notifications

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CrimeSense System                         │
├─────────────┬─────────────┬─────────────┬────────────────────┤
│  Desktop    │   Web App   │  IoT Hub    │  Flask Backend     │
│  (Tkinter) │   (Flask)   │  (Cameras)  │  (Alerts/Firebase) │
└─────────────┴─────────────┴─────────────┴────────────────────┘
```

## Components

### 1. Core Face Recognition (`facerec.py`)
- LBPH Face Recognizer using OpenCV
- Haar Cascade classifier for face detection
- Confidence threshold: 95%

### 2. Web Application (`web_app.py`)
- Flask-based dashboard on port 5000
- Criminal registration with image upload
- Image/Video surveillance endpoints
- Real-time alert system

### 3. Backend API (`flask_app.py`)
- Firebase Realtime Database integration
- Gmail API for OTP notifications
- Alert storage and retrieval
- Node status tracking

### 4. IoT Hub (`iot_hub.py`)
- Camera watchdog for file monitoring
- Watchlist synchronization
- Alert publishing to API

### 5. Desktop Application (`home.py`)
- Tkinter-based UI for edge devices
- Criminal registration
- Image and video surveillance
- Live camera feed support

## Setup Instructions

### Prerequisites

1. **Python 3.7+**
2. **OpenCV with contrib modules** (for face recognition)
3. **Firebase account** for database
4. **Gmail API credentials** for OTP

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd crimesense

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download face detection models
# Place haarcascade_frontalface_default.xml or face_cascade.xml in project root
```

### Required Files Setup

#### 1. Face Cascade Classifier
Download `haarcascade_frontalface_default.xml` or `face_cascade.xml` from OpenCV GitHub and place in project root.

#### 2. Firebase Configuration
Create a Firebase project and download `serviceAccountKey.json`:
- Go to Firebase Console → Project Settings → Service Accounts
- Generate new private key
- Save as `serviceAccountKey.json` in project root

#### 3. Gmail API Setup (for OTP Authentication)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Gmail API
4. Create OAuth 2.0 credentials:
   - Go to APIs & Services → Credentials
   - Create OAuth Client ID (Desktop app type)
   - Download JSON and note Client ID and Client Secret

5. Get Refresh Token via OAuth Playground:
   - Go to [OAuth Playground](https://developers.google.com/oauthplayground/)
   - Authorize Gmail API access
   - Exchange authorization code for tokens
   - Copy the refresh_token

Update these values in `flask_app.py`:
```python
CLIENT_ID = "your-client-id"
CLIENT_SECRET = "your-client-secret"
REFRESH_TOKEN = "your-refresh-token"
ADMIN_EMAIL = "your-admin@gmail.com"
SENDER_EMAIL = "your-sender@gmail.com"
```

### Directory Structure

Create these directories:
```bash
mkdir -p face_samples     # Training images (subdirectories per person)
mkdir -p profile_pics     # Criminal profile pictures
mkdir -p uploads          # Temporary upload storage
mkdir -p camera_input     # IoT camera input directory
```

### Training the Model

1. Add face images in `face_samples/` directory:
   ```
   face_samples/
   ├── person1_name/
   │   ├── image1.jpg
   │   ├── image2.jpg
   │   └── ...
   ├── person2_name/
   │   └── ...
   ```

2. Minimum 5 images per person recommended

3. The model trains automatically when `train_model()` is called

### Running the Application

#### Option 1: Full System (Recommended)
```bash
python start.py
```
Starts both web dashboard (port 5000) and IoT API (port 8080)

#### Option 2: Individual Components

**Web Dashboard Only:**
```bash
python web_app.py
# Access: http://localhost:5000
```

**IoT Backend Only:**
```bash
python flask_app.py
# API: http://localhost:8080
```

**Desktop Application:**
```bash
python home.py
```

#### IoT Device Startup
```bash
python start_iot.py
```

## API Endpoints

### Alert API (flask_app.py - Port 8080)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | OTP login page |
| `/verify` | POST | Verify OTP code |
| `/dashboard` | GET | Dashboard (authenticated) |
| `/api/alerts` | POST | Push new alert |
| `/api/status` | GET | Get node status |
| `/api/get_logs` | GET | Retrieve all logs |

### Web App API (web_app.py - Port 5000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dashboard` | GET | Main dashboard |
| `/register` | GET | Criminal registration |
| `/api/register/criminal` | POST | Register new criminal |
| `/surveillance/image` | GET | Image surveillance |
| `/api/surveillance/image` | POST | Process image |
| `/surveillance/video` | GET | Video surveillance |
| `/api/surveillance/video` | POST | Process video |
| `/camera` | GET | Camera page |
| `/api/camera/detect` | POST | Process camera frame |
| `/criminals` | GET | List all criminals |

## Environment Variables (Optional)

Create a `.env` file for sensitive configuration:

```env
# Firebase
FIREBASE_DATABASE_URL=https://crimesense-18d52-default-rtdb.firebaseio.com/

# Gmail API
GMAIL_CLIENT_ID=your-client-id
GMAIL_CLIENT_SECRET=your-client-secret
GMAIL_REFRESH_TOKEN=your-refresh-token

# Security
SECRET_KEY=your-secret-key
ADMIN_EMAIL=admin@example.com

# API URLs
ALERT_API_URL=http://localhost:8080/api/alerts
```

## Configuration

### Watchlist (Criminal.csv)
Format:
```csv
Name,Father's Name,Gender,DOB,Crimes Done
John Doe,Robert Doe,Male,1990-01-01,Theft
```

### Confidence Thresholds
- **< 95**: Flagged as potential criminal (red box)
- **>= 95**: Unknown person (green box)

## Security Considerations

1. **Never commit** `serviceAccountKey.json` to version control
2. **Never commit** API keys or credentials
3. Use environment variables for sensitive data in production
4. Implement HTTPS in production deployment
5. Add rate limiting to API endpoints

## Dependencies

Core dependencies:
- Flask >= 1.1.0
- opencv-contrib-python >= 4.2.0
- face-recognition >= 1.2.3
- firebase-admin >= 6.0.0
- requests >= 2.22.0

Full list in `requirements.txt`

## Troubleshooting

### Model not loading
- Ensure `face_cascade.xml` exists
- Check `face_samples/` has subdirectories with images
- Minimum 5 images per person required

### Firebase connection failed
- Verify `serviceAccountKey.json` is valid
- Check database URL in configuration
- Ensure Firebase project is active

### Gmail OTP not sending
- Verify OAuth credentials
- Check refresh token hasn't expired
- Ensure Gmail API is enabled

## License

This project is for educational/demonstration purposes. Ensure compliance with local laws and regulations regarding facial recognition and surveillance systems.

## Author

Shashank Kontikal - 2026