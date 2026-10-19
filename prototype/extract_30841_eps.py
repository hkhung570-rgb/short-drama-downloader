import urllib.request
import re
import json

url = "https://huangguodrama.ai/en/video/30841/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")

# In Next.js stream, strings are escaped as \" inside JSON string
# Let's find episodeList\":\[ ... \]
m = re.search(r'episodeList\\":(\[.*?\])\s*,\s*\\"(?:episodes|total|pagination)', html)
if not m:
    # try until \]
    m = re.search(r'episodeList\\":(\[.*?\])', html)

if m:
    raw = m.group(1)
    # unescape \" to "
    unescaped = raw.replace('\\"', '"').replace('\\/', '/')
    try:
        episodes = json.loads(unescaped)
        print(f"Successfully parsed {len(episodes)} episodes!")
        for ep in episodes:
            print(f"EP {ep.get('n'):>2}: {ep.get('title')} | video: {ep.get('video')} | cover: {ep.get('cover')}")
    except Exception as e:
        print("Parse error:", e)
        print("Raw head:", unescaped[:300])
        print("Raw tail:", unescaped[-300:])
else:
    print("Not found episodeList regex")
