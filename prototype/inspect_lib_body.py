import urllib.request
import re

url = "https://huangguodrama.ai/drama-library/3644/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
# Strip html tags
text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.S)
text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.S)
text = re.sub(r'<[^>]+>', ' ', text)
print(' '.join(text.split())[:1200])
