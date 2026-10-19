import urllib.request
import re

url = "https://huangguodrama.ai/ai-duanju/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    res = urllib.request.urlopen(req, timeout=15)
    html = res.read().decode("utf-8", "ignore")
    print("Status:", res.status)
    title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    print("Title:", title.group(1) if title else "None")
    links = re.findall(r'href=["\']([^"\']+)["\']', html)
    video_links = [l for l in set(links) if any(x in l for x in ["video", "play", "drama", "watch", "detail", "duanju"])]
    print("Video links:", len(video_links))
    for l in sorted(video_links)[:20]:
        print("  ", l)
except Exception as e:
    print("Error:", e)
