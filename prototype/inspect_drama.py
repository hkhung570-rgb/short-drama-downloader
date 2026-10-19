import urllib.request
import urllib.parse
import re

drama_path = "/drama/%E4%B8%89%E5%B9%B4%E5%8F%88%E4%B8%89%E5%B9%B4%E6%88%91%E9%83%BD%E6%88%90%E9%AC%BC%E5%AD%90%E5%A4%A7%E4%BD%90%E4%BA%86/"
url = f"https://xn--gtvs14j.online{drama_path}"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")

print("Title:", re.search(r"<title>(.*?)</title>", html, re.I | re.S).group(1))

# Look for external links, buttons, video tags, iframes
links = re.findall(r'href=["\']([^"\']+)["\']', html)
for l in set(links):
    if not l.startswith("/#") and not l.startswith("#"):
        print("Link:", l)

videos = re.findall(r'<video[^>]*src=["\']([^"\']+)["\']', html)
print("Videos:", videos)
sources = re.findall(r'<source[^>]*src=["\']([^"\']+)["\']', html)
print("Sources:", sources)
iframes = re.findall(r'<iframe[^>]*src=["\']([^"\']+)["\']', html)
print("Iframes:", iframes)

# Check all buttons or onclick or data-url
onclicks = re.findall(r'(?:onclick|data-[a-z0-9_-]*url)["\']?[:=]["\']([^"\']+)["\']', html)
print("Onclicks/data-urls:", onclicks)
