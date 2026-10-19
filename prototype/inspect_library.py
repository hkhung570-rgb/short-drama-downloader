import urllib.request
import re
import json

urls = [
    "https://huangguodrama.ai/drama-library/3644/",
    "https://huangguodrama.ai/drama-library/3641/",
    "https://huangguodrama.ai/drama-library/3639/"
]

for url in urls:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
        title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        print("URL:", url)
        print("Title:", title.group(1) if title else "None")
        # Look for video or play links
        v_links = re.findall(r'href=["\'](/[^"\']*(?:video|detail|play)[^"\']*)["\']', html)
        print("Video/detail links:", set(v_links))
        # Look for mp4 / m3u8
        media = re.findall(r'https?://[^\s"\'<>]+\.(?:mp4|m3u8)', html)
        print("Media:", media[:3])
        print("---")
    except Exception as e:
        print("Failed:", url, e)
