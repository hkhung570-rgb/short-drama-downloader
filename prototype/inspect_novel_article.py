import urllib.request
import re
import json

url = "https://huangguodrama.ai/en/novels/%E4%B8%8A%E6%B5%B7%E8%BE%A3%E5%A6%88/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")

# Find article or novel body
# Check tags: <article>, <main>, class="novel...", class="story..."
articles = re.findall(r'<article[^>]*>(.*?)</article>', html, re.S)
print(f"Articles found: {len(articles)}")
if articles:
    print("Article 0 length:", len(articles[0]))
    # print snippet
    txt = re.sub(r'<[^>]+>', '\n', articles[0])
    lines = [l.strip() for l in txt.split('\n') if l.strip()]
    print(f"Article lines: {len(lines)}")
    print("First 10 lines:")
    for l in lines[:10]:
        print("  ", l)
    print("...")
    print("Last 10 lines:")
    for l in lines[-10:]:
        print("  ", l)
