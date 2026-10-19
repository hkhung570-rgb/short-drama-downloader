import urllib.request
import re
import json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def inspect_video(vid):
    url = f"https://nv5et.wrjmtnebd.cc/video/{vid}/"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', 'ignore')
    m = re.search(r'<script id="videoInitialData" type="application/json">(.*?)</script>', html)
    if not m:
        return None
    data = json.loads(m.group(1))
    title = data.get("title")
    tags = data.get("tags", [])
    ep_matches = re.findall(r'<a [^>]*class="[^"]*hg-web-play__ep[^"]*"[^>]*href="([^"]*)"[^>]*data-ep-id="(\d+)"', html)
    eps = len(ep_matches) if ep_matches else 1
    return {"id": vid, "title": title, "tags": tags, "eps": eps, "url": url}

vids = ['7811', '7628', '6233', '5161', '8756', '3710', '8714', '8545']
for vid in vids:
    info = inspect_video(vid)
    print(info)
