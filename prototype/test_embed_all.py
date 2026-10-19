import json
import urllib.request
import re

with open('prototype/movie_next_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

ob = d['data']['online_base']
print('Total chapters in online_base:', len(ob))
book_id = d['data']['book_id']

for ep in [1, 5, 10, 20, 30, 40, 50, 51]:
    item = ob[ep-1]
    ch_id = item['chapter_id']
    url = f'https://www.reelshort.com/embed/{book_id}-{ch_id}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        html = urllib.request.urlopen(req).read().decode('utf-8')
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        if m:
            data = json.loads(m.group(1))
            props = data.get('props', {}).get('pageProps', {})
            has_play = bool(props.get('play_info'))
            code = props.get('code')
            print(f'EP {ep} ({ch_id}): code={code}, has_play_info={has_play}, duration={props.get("duration")}')
    except Exception as e:
        print(f'EP {ep} error: {e}')
