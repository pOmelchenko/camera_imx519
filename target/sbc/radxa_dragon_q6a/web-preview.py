#!/usr/bin/env python3
"""Show IMX519 framing in a browser on the local network.

This repeatedly takes a short color capture with the existing private
libcamera runtime. It is intended for positioning a chart, not for measuring
frame rate or autofocus performance.
"""

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import zlib

from focus_control import script_for


ROOT = Path(__file__).resolve().parent
CAMERA = "/base/soc@0/cci@ac4b000/i2c-bus@1/camera@1a"
SENSOR_DRIVER = Path("/sys/bus/i2c/devices/20-001a/driver")
HTML = """<!doctype html>
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IMX519 — предпросмотр</title>
<style>
body{margin:0;background:#171b20;color:#eef2f5;font:16px system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:18px}
h1{font-size:1.3rem;margin:0 0 8px}p{margin:8px 0;color:#c6d0d8}
.frame{position:relative;background:#080a0c;min-height:250px;display:grid;place-items:center}
img{display:block;max-width:100%;max-height:80vh;object-fit:contain}
.line{position:absolute;background:#ffdc72a8;pointer-events:none}
.v{width:1px;height:100%;left:50%;top:0}.h{height:1px;width:100%;top:50%;left:0}
#status{font-variant-numeric:tabular-nums}a{color:#a7d1ff}
</style><main><h1>IMX519 — кадр камеры</h1>
<p>Совместите центр миры с перекрестием. Проверьте, что все четыре края листа видны.</p>
<div class="frame" id="frame"><img id="image" alt="Ожидание кадра камеры"><i class="line v"></i><i class="line h"></i></div>
<p id="status">Подключение к камере…</p><p><a href="/frame.png" target="_blank">Открыть последний кадр отдельно</a></p>
</main><script>
let shown=0;
async function update(){
  try{
    const response=await fetch('/status.json',{cache:'no-store'});
    const s=await response.json();
    const label=s.captured_at ? `${s.captured_at} · ${s.width}×${s.height} · фокус ${s.focus}` : 'Ожидание первого кадра';
    document.getElementById('status').textContent=s.error ? `${label} · ${s.error}` : label;
    if(s.seq!==shown && s.seq>0){
      shown=s.seq;
      document.getElementById('image').src=`/frame.png?seq=${s.seq}`;
      document.getElementById('frame').style.aspectRatio=`${s.width} / ${s.height}`;
    }
  }catch(e){document.getElementById('status').textContent=`Нет связи с предпросмотром: ${e}`;}
}
update();setInterval(update,1000);
</script></html>""".encode("utf-8")


def ppm_to_png(data):
    """Decode a P6 frame from cam and return PNG bytes, width and height."""
    offset = 0

    def token():
        nonlocal offset
        while offset < len(data):
            if data[offset] in b" \t\r\n":
                offset += 1
            elif data[offset] == ord("#"):
                end = data.find(b"\n", offset)
                if end < 0:
                    raise ValueError("unterminated PPM comment")
                offset = end + 1
            else:
                break
        start = offset
        while offset < len(data) and data[offset] not in b" \t\r\n#":
            offset += 1
        if start == offset:
            raise ValueError("incomplete PPM header")
        return data[start:offset]

    if token() != b"P6":
        raise ValueError("cam did not produce a P6 color frame")
    width, height, depth = (int(token()) for _ in range(3))
    if not (1 <= width <= 4656 and 1 <= height <= 3496 and depth == 255):
        raise ValueError("unexpected PPM dimensions or color depth")
    if offset >= len(data) or data[offset] not in b" \t\r\n":
        raise ValueError("missing PPM pixel separator")
    offset += 2 if data[offset:offset + 2] == b"\r\n" else 1
    pixels = data[offset:]
    stride = width * 3
    if len(pixels) != stride * height:
        raise ValueError("incomplete PPM pixel data")

    def chunk(kind, payload):
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)

    rows = b"".join(b"\0" + pixels[row * stride:(row + 1) * stride] for row in range(height))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows, 1)) + chunk(b"IEND", b""))
    return png, width, height


class Preview:
    def __init__(self, args):
        self.args = args
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.process = None
        self.image = None
        self.seq = 0
        self.captured_at = None
        self.width = self.height = None
        self.error = None

    def capture(self):
        if not SENSOR_DRIVER.is_dir():
            raise RuntimeError("IMX519 не привязан к драйверу на Q6A; проверьте камеру и журнал ядра")
        scratch = "/dev/shm" if os.access("/dev/shm", os.W_OK) else None
        with tempfile.TemporaryDirectory(prefix="imx519-web-preview-", dir=scratch) as work:
            frame = Path(work) / "frame.ppm"
            script = Path(work) / "focus.yaml"
            script.write_text(script_for(self.args.focus))
            environment = os.environ.copy()
            preview_runtime = ROOT / "runtime" / "preview"
            if "IMX519_RUNTIME" not in environment and preview_runtime.is_dir():
                environment["IMX519_RUNTIME"] = str(preview_runtime)
            command = ["bash", str(ROOT / "cam.sh"), "-c", CAMERA,
                       "--stream", f"role=viewfinder,width={self.args.width},height={self.args.height},pixelformat=XRGB8888",
                       f"--capture={self.args.frames}", f"--script={script}", f"--file={frame}"]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       start_new_session=True, text=True, env=environment)
            with self.lock:
                self.process = process
            try:
                output, _ = process.communicate(timeout=self.args.timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGINT)
                except ProcessLookupError:
                    pass
                try:
                    process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.communicate()
                raise RuntimeError(f"захват превысил {self.args.timeout} с")
            finally:
                with self.lock:
                    self.process = None
            if process.returncode:
                raise RuntimeError((output or "cam завершился с ошибкой").strip()[-400:])
            return ppm_to_png(frame.read_bytes())

    def run(self):
        while not self.stop_event.is_set():
            try:
                image, width, height = self.capture()
                with self.lock:
                    self.image, self.width, self.height = image, width, height
                    self.seq += 1
                    self.captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    self.error = None
            except (OSError, ValueError, RuntimeError) as exc:
                with self.lock:
                    self.error = str(exc).splitlines()[-1][:300]
                self.stop_event.wait(2)

    def stop(self):
        self.stop_event.set()
        with self.lock:
            process = self.process
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGINT)
            except ProcessLookupError:
                pass


class Handler(BaseHTTPRequestHandler):
    preview = None

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            data, kind = HTML, "text/html; charset=utf-8"
        elif path == "/status.json":
            with self.preview.lock:
                status = {key: getattr(self.preview, key) for key in
                          ("seq", "captured_at", "width", "height", "error")}
                status["focus"] = self.preview.args.focus
            data, kind = json.dumps(status).encode("utf-8"), "application/json"
        elif path == "/frame.png":
            with self.preview.lock:
                data = self.preview.image
            if data is None:
                self.send_error(503, "Frame not ready")
                return
            kind = "image/png"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="listen address; use the Q6A LAN address for direct access")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--focus", type=int, default=int((ROOT / "focus-position.txt").read_text().strip()))
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1440)
    parser.add_argument("--frames", type=int, default=90, help="frames per update; default 90 for exposure warm-up")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args()
    if not (1024 <= args.port <= 65535 and 0 <= args.focus <= 4095
            and 1 <= args.width <= 1920 and 1 <= args.height <= 1440
            and 1 <= args.frames <= 300 and 1 <= args.timeout <= 120):
        parser.error("port, focus, size, frames or timeout out of range")
    preview = Preview(args)
    Handler.preview = preview
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    worker = threading.Thread(target=preview.run, daemon=True)
    worker.start()
    print(f"Предпросмотр Q6A: http://{args.host}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        preview.stop()
        server.server_close()
        worker.join(timeout=5)


if __name__ == "__main__":
    main()
