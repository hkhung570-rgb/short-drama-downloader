import urllib.request
import urllib.parse
import re

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

for t in titles:
    q = urllib.parse.quote(t)
    url = f"https://huangguo.me/search?q={q}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
        # Extract drama cards or links
        # Looking for href="/detail/..." or playlet
        matches = re.findall(r'<a[^>]+href=["\'](/detail/[^"\']+)["\'][^>]*>(.*?)</a>', html, re.S)
        found = []
        for href, inner in matches:
            clean_text = re.sub(r'<[^>]+>', ' ', inner).strip()
            if clean_text:
                found.append((clean_text, href))
        print(f"=== [{t}] ===")
        if found:
            for txt, href in found:
                print(f"  {txt[:30]} -> {href}")
        else:
            # Check if there are no search results
            if "暂无" in html or "没有找到" in html:
                print("  页面显示暂无结果")
            else:
                # check all /detail/
                all_d = re.findall(r'/detail/[a-zA-Z0-9_-]+', html)
                print("  detail links found:", set(all_d))
    except Exception as e:
        print(f"[{t}] Error: {e}")
