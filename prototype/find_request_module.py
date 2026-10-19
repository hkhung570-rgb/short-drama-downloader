import urllib.request
import re

url = "https://www.reelshort.com/_next/static/chunks/pages/_app-e3704c0c6d458909.js"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
js = urllib.request.urlopen(req).read().decode("utf-8", "ignore")

# Find module 1266 definition
idx = js.find("1266:")
if idx != -1:
    print("Found 1266: at", idx)
    print(js[idx:idx+1500])
else:
    print("1266 not found directly")
