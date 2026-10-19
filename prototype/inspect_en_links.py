import urllib.request
import urllib.parse
import re

url = "https://xn--gtvs14j.online/en/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")

links = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S | re.I)
print(f"Total links on {url}: {len(links)}")

seen = set()
for href, text in links:
    clean_text = re.sub(r'<[^>]+>', ' ', text).strip()
    clean_text = ' '.join(clean_text.split())
    full_url = urllib.parse.urljoin(url, href)
    if full_url not in seen:
        seen.add(full_url)
        print(f"[{clean_text}] -> {full_url}")
