import urllib.request
import urllib.parse
import re
import json

titles = [
    "夜勤病栋",
    "试衣间里的故事",
    "我和僵尸有个约会",
    "恶鬼新娘",
    "最后一节车厢",
    "乱来之竹林大战",
    "大主宰之萧潇的觉悟",
    "美丽新世界",
    "BIN大小姐与多兰",
    "演艺圈生存法则"
]

# Check home page of huangguo.me or search
req = urllib.request.Request("https://huangguo.me/", headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")

# Find playlet/detail/play links
links = re.findall(r'href=["\']([^"\']+)["\']', html)
print(f"Total links on huangguo.me home: {len(links)}")
detail_links = [l for l in links if "/detail/" in l or "/play/" in l]
print(f"Detail/play links on home: {len(detail_links)}")
for l in list(set(detail_links))[:15]:
    print("  ", l)

# Check search api or search page
for t in titles:
    # Try search endpoint if exists
    try:
        q = urllib.parse.quote(t)
        # try common search endpoints
        for endpoint in [f"https://huangguo.me/search?q={q}", f"https://huangguo.me/api/search?q={q}", f"https://huangguo.me/api/playlet/search?keyword={q}"]:
            try:
                r = urllib.request.Request(endpoint, headers={"User-Agent": "Mozilla/5.0"})
                resp = urllib.request.urlopen(r, timeout=5)
                data = resp.read().decode("utf-8", "ignore")
                print(f"[{t}] {endpoint} -> status {resp.status}, len {len(data)}")
                if len(data) > 0 and "data" in data or "slug" in data:
                    print(f"  sample: {data[:200]}")
            except Exception as e:
                pass
    except Exception as e:
        pass
