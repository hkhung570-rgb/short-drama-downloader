import urllib.request
import re
import json

url = "https://www.reelshort.com"
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})
with urllib.request.urlopen(req) as r:
    html = r.read().decode("utf-8", "ignore")

# Find scripts
scripts = re.findall(r'src="(/_next/static/chunks/[^"]+)"', html)
print("Found scripts:", len(scripts))

# Let's inspect next data again to see how books are routed
with open("prototype/reelshort_next_data.json", "r", encoding="utf-8") as f:
    d = json.load(f)

banners = d["fallback"]["/api/ms/hall/webInfo"]["banners"]
for i, b in enumerate(banners):
    jp = b.get("jump_param", {})
    print(f"Banner {i}: title={b.get('title')}, book_id={jp.get('book_id')}, t_book_id={jp.get('t_book_id')}, count={jp.get('chapter_count')}")

# Check sitemap if exists
try:
    s_req = urllib.request.Request("https://www.reelshort.com/sitemap.xml", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(s_req) as sr:
        s_xml = sr.read().decode("utf-8", "ignore")
        print("Sitemap length:", len(s_xml))
        urls = re.findall(r'<loc>(.*?)</loc>', s_xml)
        print("Sitemap URLs:", len(urls), urls[:5])
except Exception as e:
    print("Sitemap error:", e)
