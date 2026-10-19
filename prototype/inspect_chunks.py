import urllib.request
import re

url = 'https://www.reelshort.com'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
html = urllib.request.urlopen(req).read().decode('utf-8', 'ignore')

scripts = re.findall(r'src="(/_next/static/chunks/[^"]+\.js)"', html)
for s in scripts:
    s_url = 'https://www.reelshort.com' + s
    print('Checking script:', s)
    js = urllib.request.urlopen(urllib.request.Request(s_url, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8', 'ignore')
    routes = re.findall(r'"(/[a-zA-Z0-9_\-]+/\[[^\]]+\])"', js)
    if routes:
        print('  routes:', set(routes))
    for kw in ['/drama/', '/movie/', '/book/', '/video/', '/episode/', '/watch/', '/play/', '/tv/']:
        if kw in js:
            print(f'  contains {kw}')
            # find surrounding text
            for m in re.finditer(re.escape(kw), js):
                start = max(0, m.start() - 50)
                end = min(len(js), m.end() + 50)
                print('    snippet:', js[start:end])
                break
