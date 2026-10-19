import urllib.request
import re

url = "https://huangguodrama.ai/albums/385000/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    res = urllib.request.urlopen(req, timeout=15)
    html = res.read().decode("utf-8", "ignore")
    print("Status:", res.status)
    title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    print("Title:", title.group(1) if title else "None")
    m3u8s = re.findall(r'https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*', html)
    print("M3U8 / MP4 URLs:", m3u8s)
    # Check Next.js data
    next_data = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if next_data:
        print("Found __NEXT_DATA__, length:", len(next_data.group(1)))
        import json
        data = json.loads(next_data.group(1))
        print("Keys in props:", data.get("props", {}).keys())
        page_props = data.get("props", {}).get("pageProps", {})
        print("Keys in pageProps:", page_props.keys())
        album = page_props.get("album", {})
        print("Album title:", album.get("title"))
        episodes = page_props.get("episodes", [])
        print("Episodes count:", len(episodes))
        if episodes:
            print("First episode keys:", episodes[0].keys())
            print("First episode sample:", episodes[0])
except Exception as e:
    print("Error:", e)
