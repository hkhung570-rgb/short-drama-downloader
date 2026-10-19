import urllib.request
import re
import json

url = "https://www.reelshort.com"
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})
with urllib.request.urlopen(req, timeout=15) as r:
    html = r.read().decode("utf-8", "ignore")

# Find links
links = re.findall(r'href="([^"]+)"', html)
drama_links = [l for l in set(links) if '/drama/' in l or '/movie/' in l or '/series/' in l or '/episode/' in l or '/book/' in l or '/watch/' in l]
print("Drama related links:", drama_links[:20])

m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
if m:
    data = json.loads(m.group(1))
    print("Found __NEXT_DATA__")
    props = data.get("props", {}).get("pageProps", {})
    print("props keys:", list(props.keys()))
    with open("prototype/reelshort_next_data.json", "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)
else:
    print("No __NEXT_DATA__")
    pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html)
    print("pushes count:", len(pushes))
