import urllib.request
import re
import json

url = "https://xn--gtvs14j.online/en/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")

print("HTML length:", len(html))
title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
if title:
    print("Title:", title.group(1).strip())

# Look for links
hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
print(f"Total hrefs found: {len(hrefs)}")
unique_hrefs = sorted(list(set(hrefs)))
for h in unique_hrefs:
    if any(k in h for k in ["play", "detail", "drama", "video", "chapter", "watch", "short", "en/"]):
        print("Drama link:", h)

# Look for script tags or JSON data
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
for i, s in enumerate(scripts):
    if len(s.strip()) > 0 and any(k in s for k in ["playlet", "drama", "video", "__NEXT_DATA__", "slug", "chapter", "epPlaySrcs"]):
        print(f"Script #{i} matching keywords (len {len(s)}):")
        print(s[:500])
        print("...")
