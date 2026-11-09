import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from gpiozero import MotionSensor
from gpiozero.exc import GPIODeviceError
from signal import pause
from datetime import datetime

try:
    pir = MotionSensor(4)
except GPIODeviceError as error:
    print(f"PIR sensor could not be initialized: {error}")
    raise SystemExit(1) from error

class SensorWebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)

    def do_GET(self):
        if self.path == "/api/sensor":
            response = json.dumps({
                "connected": True,
                "motion": pir.motion_detected,
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            return
        super().do_GET()

    def log_message(self, format, *args):
        return

def motion_detected():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Motion detected at {timestamp}")

def motion_stopped():
    print("No motion detected")

pir.when_motion = motion_detected
pir.when_no_motion = motion_stopped

server = ThreadingHTTPServer(("0.0.0.0", 8000), SensorWebHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()

print("PIR sensor is connected to GPIO 4 and ready.")
print("Open http://<raspberry-pi-ip>:8000 to view the website.")
pause()