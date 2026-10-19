import urllib.request
import re
import json

def test_drama(book_id):
    url = f"https://www.reelshort.com/movie/{book_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req).read().decode('utf-8', 'ignore')
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    data = json.loads(m.group(1))
    props = data["props"]["pageProps"]["data"]
    title = props["book_title"]
    ob = props["online_base"]
    print(f"=== {title} ({book_id}) ===")
    print(f"Total in online_base: {len(ob)}")
    # test first 3, middle, and last
    test_eps = [1, 2, 3, 10, len(ob)]
    for ep in test_eps:
        ch = ob[ep-1]
        ch_id = ch["chapter_id"]
        embed_url = f"https://www.reelshort.com/embed/{book_id}-{ch_id}"
        req_e = urllib.request.Request(embed_url, headers={"User-Agent": "Mozilla/5.0"})
        html_e = urllib.request.urlopen(req_e).read().decode('utf-8', 'ignore')
        me = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html_e)
        if me:
            p_e = json.loads(me.group(1))["props"]["pageProps"]
            has_p = bool(p_e.get("play_info"))
            print(f"  EP {ep} ({ch_id}): has_play_info={has_p}, duration={p_e.get('duration')}")

print("Testing Drama 1:")
test_drama("6ab8a43a2cdfd334da0580eb")

test_drama("6ab392059db6f3a57a070ae9")
