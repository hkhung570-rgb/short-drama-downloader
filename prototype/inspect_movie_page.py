import urllib.request
import re
import json

url = "https://www.reelshort.com/movie/6aafa7fc530d47585a054f74"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req).read().decode("utf-8", "ignore")

m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
if m:
    data = json.loads(m.group(1))
    props = data.get("props", {}).get("pageProps", {})
    with open("prototype/movie_next_data.json", "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)
    print("Saved movie_next_data.json. Keys:", list(props.keys()))
    fb = props.get("fallback", {})
    print("Fallback keys:", list(fb.keys()))
    for k in fb:
        print("Fallback key:", k)
        val = fb[k]
        if isinstance(val, dict):
            print("  dict keys:", list(val.keys()))
            if "data" in val:
                print("  data type:", type(val["data"]))
                if isinstance(val["data"], dict):
                    print("  data keys:", list(val["data"].keys()))
else:
    print("No NEXT_DATA")

# Also check scripts loaded on this page
scripts = re.findall(r'src="(/_next/static/chunks/[^"]+\.js)"', html)
print("Page scripts:", scripts)
