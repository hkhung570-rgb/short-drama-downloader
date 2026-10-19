import os
import re
import json
import base64
import zlib
import urllib.request
import urllib.parse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from Crypto.Cipher import AES
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
AES_KEY = b"VvRSNGFynLBW7aCP"
AES_IV = b"gLn8sxqpzyNjehDP"

def decrypt_play_info(play_info_str):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    raw = cipher.decrypt(base64.b64decode(play_info_str))
    pad = raw[-1]
    if pad <= 16:
        raw = raw[:-pad]
    step2 = base64.b64decode(raw)
    decompressed = zlib.decompress(step2)
    return json.loads(decompressed.decode("utf-8"))

def get_best_m3u8_url(play_info_list):
    # Prefer H264 1080P, then 720P, fallback to whatever is available
    h264_streams = [s for s in play_info_list if s.get("Encode") == "H264"]
    if not h264_streams:
        h264_streams = play_info_list
    h264_streams.sort(key=lambda s: s.get("Dpi", 0), reverse=True)
    return h264_streams[0]["PlayURL"]

def download_m3u8_to_mp4(m3u8_url, out_mp4):
    req = urllib.request.Request(m3u8_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.reelshort.com/"})
    with urllib.request.urlopen(req, timeout=15) as r:
        lines = r.read().decode("utf-8", "ignore").splitlines()
    
    segments = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            seg_url = urllib.parse.urljoin(m3u8_url, line)
            segments.append(seg_url)
            
    print(f"Total TS segments: {len(segments)}")
    
    def fetch_ts(idx, url):
        r_ts = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.reelshort.com/"})
        for _ in range(3):
            try:
                with urllib.request.urlopen(r_ts, timeout=20) as resp:
                    return idx, resp.read()
            except Exception:
                pass
        return idx, b""
        
    ts_data = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch_ts, i, u) for i, u in enumerate(segments)]
        for f in as_completed(futures):
            idx, data = f.result()
            ts_data[idx] = data
            
    temp_ts = out_mp4 + ".temp.ts"
    with open(temp_ts, "wb") as f_out:
        for i in range(len(segments)):
            f_out.write(ts_data[i])
            
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", temp_ts,
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc",
        "-movflags", "+faststart",
        out_mp4
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    if os.path.exists(temp_ts):
        os.remove(temp_ts)
    print(f"Successfully created: {out_mp4} ({os.path.getsize(out_mp4) / (1024*1024):.2f} MB)")

# Test with EP 1 of Dear Brother
test_dir = os.path.join(os.path.dirname(__file__), "downloads", "Reelshort", "test_ep")
os.makedirs(test_dir, exist_ok=True)
embed_url = "https://www.reelshort.com/embed/6ab8a43a2cdfd334da0580eb-qb86zsvdur"
html = urllib.request.urlopen(urllib.request.Request(embed_url, headers={"User-Agent": "Mozilla/5.0"})).read().decode("utf-8")
me = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
p_e = json.loads(me.group(1))["props"]["pageProps"]
play_info_list = decrypt_play_info(p_e["play_info"])
best_url = get_best_m3u8_url(play_info_list)
print("Best M3U8 URL:", best_url)
download_m3u8_to_mp4(best_url, os.path.join(test_dir, "EP01_test.mp4"))
