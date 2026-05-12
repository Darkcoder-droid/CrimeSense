import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import threading
import shutil
import time
import requests
import os
import datetime
import cv2
import numpy as np
from facerec import train_model, detect_faces, recognize_face
from register import registerCriminal
from face_detection import *
from handler import *

# =============================================================================
# CONFIGURATION & THEME (2026 TACTICAL SLEEK)
# =============================================================================
NODE_ID = "EDGE-NODE-01"
API_URL = "https://testcrimsense-production.up.railway.app/api"
HEARTBEAT_INTERVAL = 10 

# Color Palette
BG_PRIMARY = "#1a1d21"      # Dark Charcoal
BG_PANEL = "#30363d"        # Medium Slate Gray
TEXT_INACTIVE = "#a3a8af"   # Light Gray
TEXT_ACTION = "#ff8f00"     # Security Orange
COLOR_CRIMINAL = "#e74c3c"  # Alert Red
COLOR_UNKNOWN = "#f1c40f"   # Warn Yellow
COLOR_SUCCESS = "#238636"   # Green

# =============================================================================
# IOT INTEGRATION (NERVOUS SYSTEM)
# =============================================================================
def send_alert_async(target_name, confidence):
    """Asynchronous POST to Firebase Command Center"""
    def _post():
        payload = {
            "node_id": NODE_ID,
            "target_name": target_name,
            "confidence": float(confidence) / 100.0,
            "timestamp": datetime.datetime.now().isoformat()
        }
        try:
            requests.post(f"{API_URL}/alerts", json=payload, timeout=3)
        except Exception:
            pass
    threading.Thread(target=_post, daemon=True).start()

def start_heartbeat():
    """Maintain 'ONLINE' status on dashboard"""
    def _heartbeat():
        while True:
            try:
                requests.post(f"{API_URL}/heartbeat", json={"node_id": NODE_ID}, timeout=2)
            except Exception:
                pass
            time.sleep(HEARTBEAT_INTERVAL)
    threading.Thread(target=_heartbeat, daemon=True).start()

start_heartbeat()

# =============================================================================
# UI GLOBAL STATE
# =============================================================================
active_page = 0
thread_event = threading.Event()
left_frame = None
right_frame = None
heading = None
webcam = None
img_label = None
img_read = None
img_list = []
model = None
names = None

# =============================================================================
# UI UTILS & NAVIGATION
# =============================================================================
def safe_update_ui(func, *args, **kwargs):
    try:
        if root.winfo_exists():
            func(*args, **kwargs)
    except Exception:
        pass

def goBack():
    global active_page, thread_event, webcam
    if active_page == 3 and not thread_event.is_set():
        thread_event.set()
        if webcam: webcam.release()
    for widget in pages[active_page].winfo_children():
        widget.destroy()
    pages[0].lift()
    active_page = 0

def basicPageSetup(pageNo):
    global left_frame, right_frame, heading
    tk.Button(pages[pageNo], text="< BACK", bg=BG_PANEL, fg="white", font=("Segoe UI", 10), 
              bd=0, padx=10, command=goBack).place(x=20, y=20)
    
    heading = tk.Label(pages[pageNo], fg=TEXT_ACTION, bg=BG_PRIMARY, font=("Segoe UI", 20, "bold"), pady=10)
    heading.pack()
    
    content = tk.Frame(pages[pageNo], bg=BG_PRIMARY, pady=20)
    content.pack(expand=True, fill="both", padx=40)
    
    left_frame = tk.Frame(content, bg=BG_PRIMARY)
    left_frame.grid(row=0, column=0, sticky="nsew")
    
    right_frame = tk.LabelFrame(content, text="SURVEILLANCE_LOG", bg=BG_PRIMARY, font=("Segoe UI", 10, "bold"), 
                             bd=1, foreground=TEXT_INACTIVE, labelanchor="n", pady=10)
    right_frame.grid(row=0, column=1, sticky="nsew", padx=20)
    
    content.grid_columnconfigure(0, weight=2, uniform="group1")
    content.grid_columnconfigure(1, weight=1, uniform="group1")
    content.grid_rowconfigure(0, weight=1)

def showImage(frame, img_size):
    global img_label, left_frame
    if frame is None or frame.size == 0:
        print("[EDGE] ERROR: Invalid image data. Skipping.")
        return

    try:
        img = cv2.resize(frame, (img_size, img_size))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(img)
        img = ImageTk.PhotoImage(img)
        
        if img_label is None or not hasattr(img_label, "winfo_exists") or not img_label.winfo_exists():
            img_label = tk.Label(left_frame, image=img, bg=BG_PRIMARY, bd=1, relief="solid")
            img_label.image = img
            img_label.pack(padx=20, pady=20)
        else:
            if isinstance(img_label, tk.Label):
                img_label.configure(image=img)
                img_label.image = img
    except Exception as e:
        print(f"[EDGE] DISPLAY_ERROR: {e}")

# =============================================================================
# FEATURE 1: ADD CRIMINALS (REGISTRATION)
# =============================================================================
def selectMultiImage(opt_menu, menu_var):
    global img_list
    filetype = [("images", "*.jpg *.jpeg *.png")]
    path_list = filedialog.askopenfilenames(title="Select at least 5 images", filetypes=filetype)
    if(len(path_list) < 5):
        messagebox.showerror("Error", "Select at least 5 images for training.")
    else:
        img_list = [cv2.imread(p) for p in path_list]
        menu_var.set("Image 1")
        opt_menu['menu'].delete(0, 'end')
        for i in range(len(img_list)):
            ch = f"Image {i+1}"
            opt_menu['menu'].add_command(label=ch, command=tk._setit(menu_var, ch))
        showImage(img_list[0], 400)

def register(entries, required, menu_var):
    global img_list
    if not img_list:
        messagebox.showerror("Error", "Select images first.")
        return
    
    entry_data = {}
    for i, entry in enumerate(entries):
        val = entry[1].get()
        if not val and required[i]:
            messagebox.showerror("Field Error", f"Missing: {entry[0]}")
            return
        entry_data[entry[0]] = val.lower()

    path = os.path.join('face_samples', entry_data["Name"])
    if not os.path.isdir(path): os.makedirs(path)

    for i, img in enumerate(img_list):
        registerCriminal(img, path, i + 1)

    insertData(entry_data)
    messagebox.showinfo("Success", "Target Registered Successfully.")
    goBack()

def getPage1():
    global active_page, img_label
    active_page = 1
    img_label = None
    pages[1].lift()
    basicPageSetup(1)
    if heading is not None:
        heading.configure(text="TARGET_REGISTRATION")
    
    menu_var = tk.StringVar(root)
    menu_var.set("Image 1")
    
    btn_grid = tk.Frame(left_frame, bg=BG_PRIMARY)
    btn_grid.pack(pady=20)
    
    fields = ["Name", "Father's Name", "Gender", "DOB(yyyy-mm-dd)", "Crimes Done"]
    entries = []
    for f in fields:
        row = tk.Frame(right_frame, bg=BG_PRIMARY, pady=8)
        row.pack(fill="x", padx=20)
        tk.Label(row, text=f, fg=TEXT_INACTIVE, bg=BG_PRIMARY, font=("Segoe UI", 9)).pack(side="left")
        ent = tk.Entry(row, bg=BG_PANEL, fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#444")
        ent.pack(side="right", expand=True, fill="x", padx=10)
        entries.append((f, ent))
    
    opt_row = tk.Frame(right_frame, bg=BG_PRIMARY, pady=10)
    opt_row.pack(fill="x", padx=20)
    tk.Label(opt_row, text="Profile Selection", fg=TEXT_INACTIVE, bg=BG_PRIMARY, font=("Segoe UI", 9)).pack(side="left")
    opt_menu = tk.OptionMenu(opt_row, menu_var, "Image 1")
    opt_menu.configure(bg=BG_PANEL, fg="white", bd=0, highlightthickness=0)
    opt_menu.pack(side="right", expand=True, fill="x", padx=10)

    tk.Button(btn_grid, text="UPLOAD IMAGES", command=lambda: selectMultiImage(opt_menu, menu_var), 
              bg=BG_PANEL, fg=TEXT_ACTION, font=("Segoe UI", 10, "bold"), bd=0, padx=20, pady=10).pack(pady=10)
    
    tk.Button(right_frame, text="EXECUTE REGISTRATION", command=lambda: register(entries, [1]*5, menu_var),
              bg=COLOR_SUCCESS, fg="white", font=("Segoe UI", 10, "bold"), bd=0, pady=12).pack(fill="x", padx=20, pady=20)

# =============================================================================
# FEATURE 2: IMAGE SURVEILLANCE
# =============================================================================
def selectImage():
    global img_read, img_label
    path = filedialog.askopenfilename(filetypes=[("images", "*.jpg *.jpeg *.png")])
    if path:
        img_read = cv2.imread(path)
        if img_read is not None:
            showImage(img_read, 500)

def startRecognition():
    global img_read, model, names
    if img_read is None: return
    if right_frame is not None:
        for wid in right_frame.winfo_children():
            wid.destroy()
    
    gray = cv2.cvtColor(img_read, cv2.COLOR_BGR2GRAY)
    face_coords = detect_faces(gray)
    
    if len(face_coords) > 0:
        if model is None: (model, names) = train_model()
        frame_with_boxes, recognized = recognize_face(model, img_read.copy(), gray, face_coords, names)
        showImage(frame_with_boxes, 500)
        
        for name, conf in recognized:
            send_alert_async(name, conf)
            lbl = tk.Label(right_frame, text=f"IDENTIFIED: {name}\nCONFIDENCE: {conf}%", 
                         bg=COLOR_CRIMINAL if conf < 95 else COLOR_UNKNOWN,
                         fg="white", font=("Courier New", 9, "bold"), pady=10, bd=1, relief="solid")
            lbl.pack(fill="x", padx=10, pady=5)
    else:
        messagebox.showinfo("Analysis", "No faces detected in high-confidence range.")

def getPage2():
    global active_page, img_label
    active_page = 2
    img_label = None
    pages[2].lift()
    basicPageSetup(2)
    if heading is not None:
        heading.configure(text="IMAGE_SURVEILLANCE")
    
    tk.Button(left_frame, text="SELECT_SOURCE_IMAGE", command=selectImage, bg=BG_PANEL, fg=TEXT_ACTION, font=("Segoe UI", 10, "bold"), bd=0, padx=20, pady=10).pack(pady=10)
    tk.Button(left_frame, text="INITIALIZE_ANALYSIS", command=startRecognition, bg=COLOR_SUCCESS, fg="white", font=("Segoe UI", 10, "bold"), bd=0, padx=20, pady=10).pack(pady=10)

# =============================================================================
# FEATURE 3: VIDEO SURVEILLANCE
# =============================================================================
def videoLoop(path, model, names):
    global thread_event, webcam, img_label
    webcam = cv2.VideoCapture(path)
    old_recognized = []
    
    try:
        while not thread_event.is_set():
            ret, frame = webcam.read()
            if not ret: break
            
            frame = cv2.flip(frame, 1)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_coords = detect_faces(gray)
            frame_with_boxes, recognized = recognize_face(model, frame, gray, face_coords, names)

            recog_names = [item[0] for item in recognized]
            if recog_names != old_recognized:
                if right_frame is not None:
                    safe_update_ui(lambda: [w.destroy() for w in right_frame.winfo_children()])
                    for name, conf in recognized:
                        send_alert_async(name, conf)
                        def _add_lbl(n=name, c=conf):
                            lbl = tk.Label(right_frame, text=f"LIVE_MATCH: {n}\nCONFIDENCE: {c}%", 
                                         bg=COLOR_CRIMINAL if c < 95 else COLOR_UNKNOWN,
                                         fg="white", font=("Courier New", 9, "bold"), pady=10, bd=1, relief="solid")
                            lbl.pack(fill="x", padx=10, pady=5)
                        safe_update_ui(_add_lbl)
                old_recognized = recog_names

            safe_update_ui(showImage, frame_with_boxes, 500)
            time.sleep(0.02)
    except Exception:
        pass
    finally:
        if webcam:
            webcam.release()

def selectVideo():
    path = filedialog.askopenfilename(filetypes=[("video", "*.mp4 *.mkv *.avi")])
    if path:
        global model, names, thread_event
        if right_frame is not None:
            for wid in right_frame.winfo_children():
                wid.destroy()
        if model is None: (model, names) = train_model()
        thread_event.clear()
        threading.Thread(target=videoLoop, args=(path, model, names), daemon=True).start()

def getPage3():
    global active_page, img_label
    active_page = 3
    img_label = None
    pages[3].lift()
    basicPageSetup(3)
    if heading is not None:
        heading.configure(text="VIDEO_SURVEILLANCE")
    
    tk.Button(left_frame, text="SELECT_VIDEO_STREAM", command=selectVideo, bg=BG_PANEL, fg=TEXT_ACTION, font=("Segoe UI", 10, "bold"), bd=0, padx=20, pady=10).pack(pady=10)

# =============================================================================
# MAIN INTERFACE
# =============================================================================
root = tk.Tk()
root.title(f"CRIMESENSE_EDGE | {NODE_ID}")
root.geometry("1100x850")
root.configure(bg=BG_PRIMARY)

pages = [tk.Frame(root, bg=BG_PRIMARY) for _ in range(4)]
for p in pages:
    p.place(x=0, y=0, relwidth=1, relheight=1)

tk.Label(pages[0], text="CRIMESENSE SECURITY TERMINAL", fg=TEXT_ACTION, bg=BG_PRIMARY, font=("Segoe UI", 22, "bold"), pady=60).pack()

btn_frame = tk.Frame(pages[0], bg=BG_PRIMARY)
btn_frame.pack(pady=10)

menu_items = [
    ("ADD_TARGET_DATA", getPage1),
    ("IMAGE_SURVEILLANCE", getPage2),
    ("VIDEO_SURVEILLANCE", getPage3)
]

for txt, cmd in menu_items:
    tk.Button(btn_frame, text=txt, command=cmd, font=("Segoe UI", 12, "bold"), width=30, 
              bg=BG_PANEL, fg="white", pady=15, bd=1, relief="solid",
              activebackground=TEXT_ACTION, activeforeground="black").pack(pady=12)

status_bar = tk.Frame(pages[0], bg="#111", height=40)
status_bar.pack(side="bottom", fill="x")
tk.Label(status_bar, text=f"IOT_STATUS: CONNECTED TO CLOUD | NODE: {NODE_ID}", fg=COLOR_SUCCESS, bg="#111", font=("Courier New", 9)).pack(pady=10)

pages[0].lift()
root.mainloop()