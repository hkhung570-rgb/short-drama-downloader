# -*- coding: utf-8 -*-
"""测试共享环境：临时下载/数据目录(必须在 import web_app 之前设置)、真实 HTTP 服务线程、合成视频。"""
import hashlib
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TMP = tempfile.TemporaryDirectory()
os.environ["DL_DOWNLOADS_DIR"] = os.path.join(TMP.name, "downloads")
os.environ["DL_DATA_DIR"] = os.path.join(TMP.name, "data")
os.environ.pop("DL_TOKEN", None)

import web_app  # noqa: E402

_live = {}
_lock = threading.Lock()


def live_server():
    """
    启动(一次)独立进程的真实平台 (python web_app.py)，使用它自己的临时下载/数据目录。
    返回 (base_url, downloads_dir)。独立进程 = 与进程内 TestClient 测试互不干扰，也更接近真实使用。
    """
    import atexit
    import urllib.request
    with _lock:
        if _live:
            return _live["base"], _live["dl"]
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        dl = os.path.join(TMP.name, "live", "downloads")
        data = os.path.join(TMP.name, "live", "data")
        os.makedirs(dl, exist_ok=True)
        env = dict(os.environ, DL_DOWNLOADS_DIR=dl, DL_DATA_DIR=data, PYTHONUTF8="1")
        env.pop("DL_TOKEN", None)
        log = open(os.path.join(TMP.name, "live.log"), "wb")
        proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "web_app.py"), "--host", "127.0.0.1", "--port", str(port)],
                                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        atexit.register(lambda: (proc.kill(), log.close()))
        base = f"http://127.0.0.1:{port}"
        end = time.time() + 30
        while time.time() < end:
            try:
                urllib.request.urlopen(base + "/api/health", timeout=1).read()
                break
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError("测试服务进程退出，日志见 " + os.path.join(TMP.name, "live.log"))
                time.sleep(0.2)
        else:
            raise RuntimeError("测试服务启动超时")
        _live.update(base=base, dl=dl, proc=proc)
        return base, dl


def make_video(path: str, seconds: int = 3):
    import imageio_ffmpeg
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc2=s=720x1280:r=24:d={seconds}",
        "-f", "lavfi", "-i", f"sine=f=440:d={seconds}",
        "-c:v", "libx264", "-b:v", "6M", "-pix_fmt", "yuv420p", "-c:a", "aac", path], check=True)


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
