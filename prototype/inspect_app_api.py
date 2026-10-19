import urllib.request
import re

url = "https://www.reelshort.com/_next/static/chunks/pages/_app-e3704c0c6d458909.js"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
js = urllib.request.urlopen(req).read().decode("utf-8", "ignore")

# Find all /api/
apis = set(re.findall(r'\"(/api/[a-zA-Z0-9_\-/]+)\"', js))
print("APIs in _app:", apis)

# Find chunk for episodes or movie
manifest_url = "https://www.reelshort.com/_next/static/chunks/webpack-eada9a0b8f74f520.js"
req = urllib.request.Request(manifest_url, headers={"User-Agent": "Mozilla/5.0"})
webpack_js = urllib.request.urlopen(req).read().decode("utf-8", "ignore")
chunks = re.findall(r'(\d+):"([a-f0-9]+)"', webpack_js)
print("Chunks mapped:", len(chunks))
