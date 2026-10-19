import urllib.request
import re
import json

url = "https://huangguodrama.ai/en/video/30841/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")

# Find episodeList
m = re.search(r'"episodeList":(\[.*?\])(?:,"|\})', html)
if m:
    try:
        ep_list = json.loads(m.group(1))
        print(f"Total episodes in episodeList: {len(ep_list)}")
        for ep in ep_list:
            print(f"EP {ep.get('n')}: {ep.get('title')} -> {ep.get('src') or ep.get('url') or ep.get('videoUrl') or ep}")
    except Exception as e:
        print("JSON parse error:", e)
        print("Raw slice:", m.group(1)[:500])
else:
    print("Could not find 'episodeList' pattern directly, searching loosely...")
    idx = html.find("episodeList")
    if idx != -1:
        print(html[idx:idx+1500])
