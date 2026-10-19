import urllib.request
import re
import json

url = "https://huangguodrama.ai/en/video/30841/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")

# Find all self.__next_f.push
pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html)
full_f = ""
for p in pushes:
    # unescape python string
    try:
        s = bytes(p, "utf-8").decode("unicode_escape")
        full_f += s
    except Exception:
        full_f += p

print("Combined Next App Router stream len:", len(full_f))

# Search for video URLs, episodes, m3u8, mp4, api
video_urls = re.findall(r'https?://[^\s"\'\\<>]+\.(?:m3u8|mp4)[^\s"\'\\<>]*', full_f)
print("Video URLs in stream:", video_urls)

# Search in the raw HTML too
html_videos = re.findall(r'https?://[^\s"\'\\<>]+\.(?:m3u8|mp4)[^\s"\'\\<>]*', html)
print("Video URLs in raw HTML:", html_videos)

# Search for episodes info or chapter or drama details
# Look for episode references
eps = re.findall(r'(\bepisodes?\b[^\n]{0,100})', full_f, re.I)
print("Episode references:", eps[:5])

# Also check detail page
detail_url = "https://huangguodrama.ai/en/detail/30841/"
req_detail = urllib.request.Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
html_detail = urllib.request.urlopen(req_detail, timeout=15).read().decode("utf-8", "ignore")
print("\nDetail page title:", re.search(r"<title>(.*?)</title>", html_detail))
detail_videos = re.findall(r'https?://[^\s"\'\\<>]+\.(?:m3u8|mp4)[^\s"\'\\<>]*', html_detail)
print("Detail page videos:", detail_videos)

# Check all links on detail page
links = re.findall(r'href=["\']([^"\']+)["\']', html_detail)
play_links = [l for l in set(links) if "30841" in l or "video" in l or "play" in l]
print("Play/video links in detail page:", play_links)
