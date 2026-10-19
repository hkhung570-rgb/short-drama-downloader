import urllib.request
import re

url = "https://www.reelshort.com/_next/static/chunks/pages/movie/%5Bslug%5D-0eaa6ab39f1ef551.js"
js = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})).read().decode("utf-8", "ignore")
print("Length of movie slug chunk:", len(js))

apis = set(re.findall(r'"(/api/[a-zA-Z0-9_\-/]+)"', js))
print("APIs in movie slug chunk:", apis)

# find imports/requires
requires = re.findall(r'n\((\d+)\)', js)
print("Modules imported in movie slug:", set(requires))
