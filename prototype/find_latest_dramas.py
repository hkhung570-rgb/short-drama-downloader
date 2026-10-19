import urllib.request
import re
import json
from datetime import datetime

with open('prototype/reelshort_next_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

banners = d['fallback']['/api/ms/hall/webInfo'].get('banners', [])
drama_list = []

for b in banners:
    jp = b.get('jump_param', {})
    book_id = jp.get('book_id')
    if not book_id:
        continue
    url = f"https://www.reelshort.com/movie/{book_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', 'ignore')
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        if m:
            data = json.loads(m.group(1))
            props = data.get("props", {}).get("pageProps", {}).get("data", {})
            online_at = props.get("online_at", 0)
            publish_at = props.get("publish_at", 0)
            title = props.get("book_title", jp.get("book_title"))
            total = props.get("total", 0)
            cover = props.get("book_pic", "")
            drama_list.append({
                "book_id": book_id,
                "title": title,
                "online_at": online_at,
                "online_date": str(datetime.fromtimestamp(online_at)) if online_at else "",
                "publish_at": publish_at,
                "publish_date": str(datetime.fromtimestamp(publish_at)) if publish_at else "",
                "total": total,
                "cover": cover,
                "url": url,
                "online_base": props.get("online_base", [])
            })
    except Exception as e:
        print(f"Error fetching {book_id}: {e}")

# Sort by online_at descending (latest first)
drama_list.sort(key=lambda x: max(x['online_at'], x['publish_at']), reverse=True)

print("=== ReelShort Dramas Sorted by Date (Newest to Oldest) ===")
for i, item in enumerate(drama_list):
    print(f"[{i+1}] {item['title']}")
    print(f"    Book ID: {item['book_id']}")
    print(f"    Online Date: {item['online_date']} (Timestamp: {item['online_at']})")
    print(f"    Publish Date: {item['publish_date']} (Timestamp: {item['publish_at']})")
    print(f"    Total Episodes: {item['total']}")
    print(f"    URL: {item['url']}")
    print()

with open('prototype/latest_dramas.json', 'w', encoding='utf-8') as f:
    json.dump([{k: v for k, v in item.items() if k != 'online_base'} for item in drama_list], f, ensure_ascii=False, indent=2)
