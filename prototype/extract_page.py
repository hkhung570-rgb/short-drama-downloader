import urllib.request
import urllib.parse
import re
import json

url = "https://xn--gtvs14j.online/en/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")

# 1. All images
imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', html, re.I)
img_urls = [urllib.parse.urljoin(url, src) for src in imgs]

# 2. All links
links = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S | re.I)
parsed_links = []
for href, text in links:
    clean_text = re.sub(r'<[^>]+>', ' ', text).strip()
    clean_text = ' '.join(clean_text.split())
    full_url = urllib.parse.urljoin(url, href)
    parsed_links.append((clean_text, full_url))

# 3. Scripts / assets
scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.I)
script_urls = [urllib.parse.urljoin(url, src) for src in scripts]
css = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', html, re.I)
css_urls = [urllib.parse.urljoin(url, src) for src in css]

print(f"Images ({len(img_urls)}):")
for u in set(img_urls):
    print("  ", u)

print(f"\nScripts ({len(script_urls)}):", script_urls)
print(f"\nCSS/Links ({len(css_urls)}):", css_urls[:10])

# Separate drama links vs others
drama_links = [(t, u) for t, u in parsed_links if '/drama/' in u]
print(f"\nDrama links on /en/ ({len(drama_links)}):")
for t, u in drama_links[:10]:
    print(f"  {t}: {u}")
