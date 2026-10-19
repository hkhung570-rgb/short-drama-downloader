import urllib.request
import urllib.parse
import re
import json

url = "https://huangguodrama.ai/en/novels/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")

# Find all novel cards / links
# <a href="/en/novels/..."
links = re.findall(r'<a[^>]+href=["\'](/en/novels/[^"\'#]+)["\'][^>]*>(.*?)</a>', html, re.S)
novels = {}
for path, text in links:
    clean_path = path.strip()
    if clean_path in ["/en/novels/", "/en/novels"]:
        continue
    # clean title
    t = re.sub(r'<[^>]+>', ' ', text).strip()
    slug = clean_path.split("/en/novels/")[1].strip("/")
    decoded_slug = urllib.parse.unquote(slug)
    if decoded_slug not in novels:
        novels[decoded_slug] = {
            "slug": decoded_slug,
            "url": urllib.parse.urljoin(url, clean_path),
            "display_text": t
        }

print(f"Total novels found on /en/novels/: {len(novels)}")
for i, (k, v) in enumerate(sorted(novels.items())):
    print(f"  {i+1:02d}. {k} -> {v['url']}")
