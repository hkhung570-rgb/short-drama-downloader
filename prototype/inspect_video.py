import urllib.request
import re

url = "https://huangguodrama.ai/video/10438/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    res = urllib.request.urlopen(req, timeout=15)
    html = res.read().decode("utf-8", "ignore")
    print("Status:", res.status)
    title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    print("Title:", title.group(1) if title else "None")
    m3u8s = re.findall(r'https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*', html)
    print("M3U8 / MP4 URLs:", len(m3u8s))
    for m in m3u8s[:5]:
        print("  ", m)
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
    for s in scripts:
        if "epPlaySrcs" in s or "videoInitialData" in s or "m3u8" in s:
            print("Found script containing video data! Len:", len(s))
            print(s[:300])
except Exception as e:
    print("Error:", e)
