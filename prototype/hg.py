#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""huangguo.me 播放地址抓取 (游客/免费集)。
用法: python hg.py <slug或detail/play URL> [--m3u8] [--base https://镜像域名]
  域名: huangguo.me 是唯一的网页播放站; huangguo.com 只是 App 下载落地页(无播放 API)。
  传入完整 URL 时自动采用该 URL 的域名。
  默认输出每集 playUrl(经本站代理的 m3u8)。--m3u8 会额外拉取并打印 m3u8 清单首行。
"""
import sys, re, json, urllib.request, urllib.parse

BASE = "https://huangguo.me"
UA = "Mozilla/5.0"  # 关键: UA 不能含 "Windows" 否则 CF 回 444

def http(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def slug_of(arg):
    m = re.search(r"/(?:detail|play)/([^/]+)", arg)
    return m.group(1) if m else arg.strip().strip("/")

def chapter_ids(slug):
    """从详情页 HTML 解析所有剧集 chapterId 及集号。"""
    html = http(f"{BASE}/detail/{slug}/").decode("utf-8", "replace")
    eps = {}
    # 免费集: <a href="/play/slug/<id>/" data-ep="N">
    for cid, ep in re.findall(r'/play/%s/(\d+)/"\s+data-ep="(\d+)"' % re.escape(slug), html):
        eps[int(ep)] = int(cid)
    # 锁定集: data-chapter-id="<id>" ... data-ep="N"
    for m in re.finditer(r'data-coin-dialog-open[^>]*?data-ep="(\d+)"[^>]*?data-chapter-id="(\d+)"', html):
        eps.setdefault(int(m.group(1)), int(m.group(2)))
    for m in re.finditer(r'data-chapter-id="(\d+)"[^>]*?data-ep="(\d+)"', html):
        eps.setdefault(int(m.group(2)), int(m.group(1)))
    return [eps[k] for k in sorted(eps)], slug

def chapter_detail(cid, slug):
    q = urllib.parse.urlencode({"chapterId": cid, "playletSlug": slug})
    return json.loads(http(f"{BASE}/api/playlet/chapter/detail?{q}"))["data"]

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    global BASE
    argv = sys.argv[1:]
    want_m3u8 = "--m3u8" in argv
    if "--base" in argv:
        i = argv.index("--base"); BASE = argv[i + 1].rstrip("/"); del argv[i:i + 2]
    target = [a for a in argv if not a.startswith("--")][0]
    m = re.match(r"(https?://[^/]+)/(?:detail|play)/", target)
    if m:
        BASE = m.group(1)
    slug = slug_of(target)
    ids, slug = chapter_ids(slug)
    print(f"# slug={slug}  共 {len(ids)} 集")
    for cid in ids:
        d = chapter_detail(cid, slug)
        ep = d.get("currentEpisode")
        vurl = d.get("videoUrl") or ""
        if not vurl:
            why = "needVip" if d.get("needVip") else ("needUnlock %d币" % d.get("singleCoins", 0) if d.get("needUnlock") else "空地址")
            print(f"EP{ep:>2} ch={cid} [锁定 payType={d.get('payType')} {why}]")
            continue
        play = f"{BASE}/h5/m3u8/{vurl}"
        print(f"EP{ep:>2} ch={cid} {play}")
        if want_m3u8:
            m = http(play).decode("utf-8", "replace")
            key = re.search(r'URI="([^"]+)"', m)
            seg = re.search(r'^(https?://\S+)', m, re.M)
            print(f"     KEY {BASE+key.group(1) if key else '-'}")
            print(f"     TS  {seg.group(1) if seg else '-'}")

if __name__ == "__main__":
    main()
