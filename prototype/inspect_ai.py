import urllib.request
import re

url = "https://huangguodrama.ai/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    res = urllib.request.urlopen(req, timeout=15)
    html = res.read().decode("utf-8", "ignore")
    print("Status:", res.status)
    print("URL:", res.geturl())
    print("Title:", re.search(r"<title>(.*?)</title>", html, re.I | re.S))
    links = re.findall(r'href=["\']([^"\']+)["\']', html)
    print("Unique links:", len(set(links)))
    for l in sorted(list(set(links)))[:30]:
        print("  ", l)
except Exception as e:
    print("Error:", e)
