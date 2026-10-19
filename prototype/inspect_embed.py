import urllib.request
import re
import json

url = 'https://www.reelshort.com/embed/6aafa7fc530d47585a054f74-vxywyv2hus'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
if m:
    data = json.loads(m.group(1))
    props = data.get('props', {}).get('pageProps', {})
    print('embed pageProps keys:', list(props.keys()))
    with open('prototype/embed_next_data.json', 'w', encoding='utf-8') as f:
        json.dump(props, f, ensure_ascii=False, indent=2)
    for k in props:
        val = props[k]
        if isinstance(val, dict):
            print(k, 'keys:', list(val.keys()))
        else:
            print(k, ':', str(val)[:100])
