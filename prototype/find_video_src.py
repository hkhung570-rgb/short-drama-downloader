import urllib.request
import re

html = urllib.request.urlopen(urllib.request.Request("https://www.reelshort.com", headers={"User-Agent": "Mozilla/5.0"})).read().decode("utf-8")
scripts = re.findall(r'src="(/_next/static/chunks/[^"]+\.js)"', html)

for s in scripts:
    url = "https://www.reelshort.com" + s
    js = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})).read().decode("utf-8", "ignore")
    # check for m3u8 or player
    for kw in ['m3u8', 'mp4', 'Hls', 'video/mp4', 'video/x-mpegURL', 'videoSrc', 'videoUrl']:
        if kw in js:
            print(f"File {s} has {kw}:")
            for m in re.finditer(re.escape(kw), js):
                start = max(0, m.start() - 100)
                end = min(len(js), m.end() + 100)
                print("   ", js[start:end])
                break
