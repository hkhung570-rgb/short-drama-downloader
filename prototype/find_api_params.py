import urllib.request
import re

url = "https://www.reelshort.com/_next/static/chunks/pages/_app-e3704c0c6d458909.js"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
js = urllib.request.urlopen(req).read().decode("utf-8", "ignore")

for api in ['webNewReleaseBooks', 'getBookInfo', 'getChapterList', 'getChapterInfo']:
    for m in re.finditer(re.escape(api), js):
        start = max(0, m.start() - 200)
        end = min(len(js), m.end() + 200)
        print(f"=== {api} ===")
        print(js[start:end])
        print()
