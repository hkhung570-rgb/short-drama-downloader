import urllib.request
import re
import json

url = "https://huangguodrama.ai/en/video/30841/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")

# Find episodeList
idx = html.find('episodeList\\":')
if idx != -1:
    chunk = html[idx+len('episodeList\\":'):]
    # find ending
    # Let's extract all objects like {"n":X,"title":...}
    # Pattern: \{"n":(\d+).*?video\\":\\"(.*?)\\"
    ep_matches = re.finditer(r'\{\\"n\\":(\d+),\\"title\\":\\"(.*?)\\",\\"desc\\":\\"(.*?)\\",\\"cover\\":\\"(.*?)\\",\\"video\\":\\"(.*?)\\"\}', chunk)
    episodes = []
    for m in ep_matches:
        episodes.append({
            "n": int(m.group(1)),
            "title": m.group(2).encode().decode('unicode_escape'),
            "desc": m.group(3).encode().decode('unicode_escape'),
            "cover": m.group(4).encode().decode('unicode_escape'),
            "video": m.group(5).encode().decode('unicode_escape')
        })
    print(f"Extracted {len(episodes)} episodes via regex!")
    for ep in episodes:
        print(f"EP {ep['n']:>2}: {ep['title']} -> {ep['video']}")
