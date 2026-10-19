import urllib.request
import re

for s in ['/_next/static/chunks/pages/movie/%5Bslug%5D-0eaa6ab39f1ef551.js', '/_next/static/chunks/4334-561ed27db03a17f1.js', '/_next/static/chunks/4650.cf65af3f1b8290a7.js']:
    url = "https://www.reelshort.com" + s
    js = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})).read().decode("utf-8", "ignore")
    print(f"=== {s} ===")
    for kw in ['play_info', 'chapter_id', 'getChapterContent', 'getChapterInfo', 'm3u8', 'video_url', 'playUrl']:
        matches = list(re.finditer(re.escape(kw), js))
        if matches:
            print(f"  {kw}: count={len(matches)}")
            for m in matches[:2]:
                start = max(0, m.start() - 80)
                end = min(len(js), m.end() + 80)
                print("    ", js[start:end])
