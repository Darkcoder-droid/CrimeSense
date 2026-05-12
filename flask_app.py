from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
import base64
import requests
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import time
import threading
import random
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
app.secret_key = "YOUR_APP_SECRET_KEY"

# ==========================================
# 1. GMAIL API CONFIGURATION (Bypasses Port Blocks)
# ==========================================
# Replace these with the keys you just got from Google Cloud & OAuth Playground
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
REFRESH_TOKEN = "YOUR_REFRESH_TOKEN"
ADMIN_EMAIL = "YOUR_ADMIN_EMAIL" 
SENDER_EMAIL = "YOUR_SENDER_EMAIL"

# ==========================================
# 2. FIREBASE INITIALIZATION
# ==========================================
try:
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://crimesense-18d52-default-rtdb.firebaseio.com/'
    })
    print("[*] FIREBASE_INITIALIZED")
except Exception as e:
    print(f"[!] FIREBASE_ERROR: {e}")

nodes_online = {}

# ==========================================
# 3. UI TEMPLATES (UNCHANGED)
# ==========================================
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CRIMESENSE | AUTH</title>
    <style>
        body { margin: 0; height: 100vh; background: #050505; display: flex; justify-content: center; align-items: center; font-family: 'JetBrains Mono', monospace; color: #c9d1d9; padding: 20px; box-sizing: border-box; }
        .glass-box { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(15px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 16px; padding: 30px; width: 100%; max-width: 350px; text-align: center; }
        .header { font-size: 18px; letter-spacing: 4px; color: #58a6ff; margin-bottom: 30px; }
        input { width: 100%; padding: 12px; margin-bottom: 20px; background: rgba(0,0,0,0.5); border: 1px solid #30363d; border-radius: 8px; color: #ffb300; text-align: center; font-size: 20px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; border-radius: 8px; background: #ffb300; color: #000; border: none; font-weight: bold; cursor: pointer; letter-spacing: 1px;}
        .msg { font-size: 11px; margin-bottom: 20px; color: #8b949e; line-height: 1.5; }
        .error { color: #f85149; font-size: 11px; margin-bottom: 15px; border: 1px solid #f85149; padding: 5px; background: rgba(248, 81, 73, 0.1); }
    </style>
</head>
<body>
    <div class="glass-box">
        <div class="header">OTP_VERIFY</div>
        {% if error %}<div class="error">[ {{ error }} ]</div>{% endif %}
        <div class="msg">A security code was dispatched. <br> Valid for 10 minutes.</div>
        <form method="POST" action="/verify">
            <input type="text" name="otp" placeholder="000000" maxlength="6" required autofocus autocomplete="off">
            <button type="submit">VERIFY_IDENTITY</button>
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CRIMESENSE | COMMAND</title>
    <style>
        :root { --bg-blur: rgba(13, 17, 23, 0.9); --accent: #58a6ff; --border: #30363d; --success: #238636; }
        body { background: #0d1117; background-image: radial-gradient(circle at 50% 50%, #161b22 0%, #0d1117 100%); color: #c9d1d9; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; margin: 0; padding: 10px; text-transform: uppercase; min-height: 100vh; box-sizing: border-box; }
        .grid { display: flex; flex-direction: column; gap: 15px; max-width: 1400px; margin: 0 auto; }
        @media (min-width: 992px) { .grid { display: grid; grid-template-columns: 300px 1fr; height: calc(100vh - 120px); } .panel { height: 100%; overflow-y: auto; } }
        .panel { background: var(--bg-blur); backdrop-filter: blur(10px); border: 1px solid var(--border); padding: 15px; border-radius: 8px; }
        .header { display: flex; flex-direction: column; gap: 10px; border-bottom: 2px solid var(--success); padding: 10px 0 15px 0; margin-bottom: 15px; }
        @media (min-width: 600px) { .header { flex-direction: row; justify-content: space-between; align-items: center; } }
        .title { font-size: 20px; font-weight: bold; color: var(--accent); letter-spacing: 2px; }
        .logout { color: #f85149; text-decoration: none; font-size: 11px; border: 1px solid #f85149; padding: 8px 12px; border-radius: 4px; transition: 0.3s; text-align: center; }
        .logout:hover { background: #f85149; color: white; }
        .date-section { margin-bottom: 8px; border: 1px solid var(--border); border-radius: 4px; overflow: hidden; }
        .date-header { background: #161b22; padding: 15px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
        .date-content { display: none; background: rgba(0,0,0,0.3); overflow-x: auto; -webkit-overflow-scrolling: touch; }
        .date-section.active .date-content { display: block; }
        table { width: 100%; border-collapse: collapse; font-size: 11px; min-width: 450px; }
        th { text-align: left; color: #8b949e; padding: 12px 10px; border-bottom: 1px solid var(--border); }
        td { padding: 12px 10px; border-bottom: 1px solid #21262d; }
        .critical { color: #f85149; font-weight: bold; }
        .node-item { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; background: rgba(255,255,255,0.03); padding: 12px; border-radius: 4px; border: 1px solid var(--border); }
        .dot { width: 10px; height: 10px; border-radius: 50%; background: #30363d; }
        .dot.online { background: var(--success); box-shadow: 0 0 8px var(--success); }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">FIREBASE_TACTICAL // V3.0</div>
        <div style="display:flex; align-items:center; gap: 15px; justify-content: space-between;">
            <div id="clock" style="color: #8b949e; font-family: monospace; font-size: 12px;"></div>
            <a href="/logout" class="logout">LOCK_TERMINAL</a>
        </div>
    </div>
    <div class="grid">
        <div class="panel">
            <div style="color: #8b949e; font-size: 10px; margin-bottom: 15px; letter-spacing: 2px;">LIVE_NODES</div>
            <div id="node-list"></div>
        </div>
        <div class="panel">
            <div style="color: #8b949e; font-size: 10px; margin-bottom: 15px; letter-spacing: 2px;">CLOUD_ARCHIVE</div>
            <div id="log-container"></div>
        </div>
    </div>
    <script>
        setInterval(() => { document.getElementById('clock').innerText = new Date().toISOString().replace('T', ' ').split('.')[0]; }, 1000);
        let expandedDates = new Set();
        function toggleDate(date) {
            const el = document.getElementById(`section-${date}`);
            if (expandedDates.has(date)) { expandedDates.delete(date); el.classList.remove('active'); }
            else { expandedDates.add(date); el.classList.add('active'); }
        }
        async function fetchData() {
            try {
                const statusRes = await fetch('/api/status');
                if (statusRes.status === 401) { window.location.href = '/'; return; }
                const statusData = await statusRes.json();
                document.getElementById('node-list').innerHTML = Object.entries(statusData.nodes).map(([id, status]) => `
                    <div class="node-item"><div class="dot ${status.toLowerCase()}"></div><span>${id}</span></div>
                `).join('') || '<div style="color: #484f58;">NO_NODES_DETECTED</div>';
                const logsRes = await fetch('/api/get_logs');
                const logsData = await logsRes.json();
                const container = document.getElementById('log-container');
                if (!logsData || Object.keys(logsData).length === 0) {
                    container.innerHTML = '<div style="text-align: center; color: #484f58; padding: 40px;">CLOUD_EMPTY</div>';
                    return;
                }
                const dates = Object.keys(logsData).sort().reverse();
                container.innerHTML = dates.map(date => {
                    const logEntries = Object.values(logsData[date]).reverse();
                    const isActive = expandedDates.has(date) ? 'active' : '';
                    return `<div class="date-section ${isActive}" id="section-${date}">
                        <div class="date-header" onclick="toggleDate('${date}')"><span>📁 ${date}</span><span style="font-size: 10px; color: #8b949e;">${logEntries.length} LOGS</span></div>
                        <div class="date-content"><table><thead><tr><th>TIME</th><th>NODE</th><th>SUBJECT</th><th>CONF</th></tr></thead><tbody>
                        ${logEntries.map(log => `<tr><td style="color: #8b949e;">${log.timestamp.split('T')[1].split('.')[0]}</td><td style="color: var(--accent);">${log.node_id}</td><td class="critical">${log.target_name}</td><td>${(log.confidence * 100).toFixed(1)}%</td></tr>`).join('')}
                        </tbody></table></div></div>`;
                }).join('');
            } catch (e) { console.error("SYNC_ERROR", e); }
        }
        setInterval(fetchData, 5000);
        fetchData();
    </script>
</body>
</html>
"""

# ==========================================
# 4. LOGIC & API (Modern Gmail API Method)
# ==========================================

def send_otp_email(otp_code):
    """Sends OTP using Gmail API via HTTPS (Port 443)"""
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    
    try:
        # Step A: Get Access Token
        r = requests.post(token_url, data=data)
        access_token = r.json().get("access_token")
        
        # Step B: Build Email
        message = MIMEText(f"TACTICAL COMMAND CENTER ACCESS\n\nCODE: {otp_code}\nVALIDITY: 10 MINUTES")
        message['to'] = ADMIN_EMAIL
        message['from'] = SENDER_EMAIL
        message['subject'] = "CRIMESENSE: Security Clearance Code"
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        # Step C: Send via Gmail API
        send_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.post(send_url, headers=headers, json={"raw": raw_message})
        
        if resp.status_code == 200:
            print("[*] OTP_SENT_VIA_API")
            return True
        else:
            print(f"[!] API_SEND_FAILED: {resp.text}")
            return False
    except Exception as e:
        print(f"[!] SYSTEM_MAIL_ERROR: {e}")
        return False

@app.route('/')
def root():
    if session.get('auth'): return redirect(url_for('dashboard'))
    now = datetime.now()
    if 'otp_expiry' in session:
        expiry = datetime.fromisoformat(session['otp_expiry'])
        if now < expiry: return render_template_string(LOGIN_HTML)

    otp = str(random.randint(100000, 999999))
    session['otp_code'] = otp
    session['otp_expiry'] = (now + timedelta(minutes=10)).isoformat()
    send_otp_email(otp)
    return render_template_string(LOGIN_HTML)

@app.route('/verify', methods=['POST'])
def verify():
    user_otp = request.form.get('otp')
    now = datetime.now()
    if 'otp_code' in session and 'otp_expiry' in session:
        expiry = datetime.fromisoformat(session['otp_expiry'])
        if now > expiry:
            session.pop('otp_code', None)
            return render_template_string(LOGIN_HTML, error="CODE_EXPIRED")
        if user_otp == session['otp_code']:
            session['auth'] = True
            return redirect(url_for('dashboard'))
    return render_template_string(LOGIN_HTML, error="INVALID_OTP")

@app.route('/dashboard')
def dashboard():
    if not session.get('auth'): return redirect(url_for('root'))
    return render_template_string(DASHBOARD_HTML)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('root'))

@app.route('/api/alerts', methods=['POST'])
def receive_alert():
    data = request.json
    today = datetime.now().strftime('%Y-%m-%d')
    ref = db.reference(f'alerts/{today}')
    alert_data = {
        "node_id": data.get("node_id", "EDGE_01"),
        "target_name": data.get("target_name", "UNKNOWN"),
        "confidence": data.get("confidence", 0),
        "timestamp": datetime.now().isoformat()
    }
    # Track online status
    nodes_online[alert_data["node_id"]] = time.time()
    threading.Thread(target=lambda: ref.push(alert_data), daemon=True).start()
    return jsonify({"status": "SUCCESS"}), 201

@app.route('/api/status')
def get_status():
    if not session.get('auth'): return jsonify({"error": "Unauthorized"}), 401
    current_time = time.time()
    return jsonify({"nodes": {nid: ("ONLINE" if current_time - ts < 15 else "OFFLINE") for nid, ts in nodes_online.items()}})

@app.route('/api/get_logs')
def get_logs():
    if not session.get('auth'): return jsonify({"error": "Unauthorized"}), 401
    return jsonify(db.reference('alerts').get() or {})

if __name__ == '__main__':
    # Railway uses Port 8080 by default
    app.run(host='0.0.0.0', port=8080)