import os
import time
import sounddevice as sd
import numpy as np
from PIL import ImageGrab
from scipy.io.wavfile import write

import traceback


print("🕵️ Running app.py")

# === Prompt to keep or delete ===
choice = input("❓ Delete script after running? [y/N] ").strip().lower()
SHOULD_DELETE = choice == "y"

# Check DISABLE_DELETE env var
if os.getenv("DISABLE_DELETE", "0") == "1":
    SHOULD_DELETE = False

# === 1. Screenshot ===
screenshot_path = f"/tmp/screen_{time.strftime('%Y%m%d_%H%M%S')}.png"
try:
    img = ImageGrab.grab()
    img.save(screenshot_path)
    print(f"[+] Screenshot saved: {screenshot_path}")
except Exception as e:
    print(f"[!] Screenshot failed: {e}")
    traceback.print_exc()

# === 2. Mic Recording ===
mic_path = f"/tmp/mic_{time.strftime('%Y%m%d_%H%M%S')}.wav"
duration = 10  # seconds
try:
    print(f"[+] Recording mic for {duration} seconds...")
    fs = 44100
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()
    write(mic_path, fs, recording)
    print(f"[+] Mic recording saved: {mic_path}")
except Exception as e:
    print(f"[!] Mic recording failed: {e}")
    traceback.print_exc()

# === 3. Self-Delete ===
if SHOULD_DELETE:
    abs_path = os.path.abspath(__file__)
    print(f"[+] Self-deleting: {abs_path}")
    try:
        os.remove(abs_path)
    except Exception as e:
        print(f"[!] Failed to self-delete: {e}")
        traceback.print_exc()
else:
    print("[i] Self-delete skipped due to DISABLE_DELETE env var")
