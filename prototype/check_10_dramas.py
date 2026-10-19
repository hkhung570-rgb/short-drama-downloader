import urllib.request
import urllib.parse
import re
import json

targets = [
    ("夜勤病栋", "https://xn--gtvs14j.online/drama/%E5%A4%9C%E5%8B%A4%E7%97%85%E6%A0%8B/"),
    ("试衣间里的故事", "https://xn--gtvs14j.online/drama/%E8%AF%95%E8%A1%A3%E9%97%B4%E9%87%8C%E7%9A%84%E6%95%85%E4%BA%8B/"),
    ("我和僵尸有个约会", "https://xn--gtvs14j.online/drama/%E6%88%91%E5%92%8C%E5%83%B5%E5%B0%B8%E6%9C%89%E4%B8%AA%E7%BA%A6%E4%BC%9A/"),
    ("恶鬼新娘", "https://xn--gtvs14j.online/drama/%E6%81%B6%E9%AC%BC%E6%96%B0%E5%A8%98/"),
    ("最后一节车厢", "https://xn--gtvs14j.online/drama/%E6%9C%80%E5%90%8E%E4%B8%80%E8%8A%82%E8%BD%A6%E5%8E%A2/"),
    ("乱来之竹林大战", "https://xn--gtvs14j.online/drama/%E4%B9%B1%E6%9D%A5%E4%B9%8B%E7%AB%B9%E6%9E%97%E5%A4%A7%E6%88%98/"),
    ("大主宰之萧潇的觉悟", "https://xn--gtvs14j.online/drama/%E5%A4%A7%E4%B8%BB%E5%AE%B0%E4%B9%8B%E8%90%A7%E6%BD%87%E7%9A%84%E8%A7%89%E6%82%9F/"),
    ("美丽新世界", "https://xn--gtvs14j.online/drama/%E7%BE%8E%E4%B8%BD%E6%96%B0%E4%B8%96%E7%95%8C/"),
    ("BIN大小姐与多兰", "https://xn--gtvs14j.online/drama/BIN%E5%A4%A7%E5%B0%8F%E5%A7%90%E4%B8%8E%E5%A4%9A%E5%85%B0/"),
    ("演艺圈生存法则", "https://xn--gtvs14j.online/drama/%E6%BC%94%E8%89%BA%E5%9C%88%E7%94%9F%E5%AD%98%E6%B3%95%E5%88%99/")
]

results = []
for name, url in targets:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
        cover_m = re.search(r'img\s+src="(/covers/[^"]+)"', html)
        cover = urllib.parse.urljoin(url, cover_m.group(1)) if cover_m else None
        
        # Check FAQ or notes
        faq_m = re.findall(r'<p>(.*?)</p>', html)
        note = faq_m[1] if len(faq_m) > 1 else ""
        
        results.append({
            "title": name,
            "url": url,
            "cover": cover,
            "note": note
        })
        print(f"[{name}] Cover: {cover}")
    except Exception as e:
        print(f"[{name}] Failed: {e}")

with open("prototype/10_dramas_status.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
