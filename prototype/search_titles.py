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

# 1. Check huangguodrama.ai search API or pages
for title in titles:
    # try search on huangguodrama.ai
    q = urllib.parse.quote(title)
    url = f"https://huangguodrama.ai/search/?q={q}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
        # search for /video/ or /detail/
        links = re.findall(r'href=["\'](/[^"\']*(?:video|detail|drama)[^"\']*)["\']', html)
        print(f"[{title}] search links on huangguodrama.ai:", set(links))
    except Exception as e:
        print(f"[{title}] search failed:", e)
