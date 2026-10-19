import urllib.request
import re

try:
    req = urllib.request.Request('https://nv5et.wrjmtnebd.cc/', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', 'ignore')
    videos = re.findall(r'href=["\'](/video/\d+/)["\']', html)
    print('nv5et videos:', list(dict.fromkeys(videos))[:15])
except Exception as e:
    print('nv5et err:', e)

try:
    req2 = urllib.request.Request('https://huangguodrama.ai/', headers={'User-Agent': 'Mozilla/5.0'})
    html2 = urllib.request.urlopen(req2, timeout=10).read().decode('utf-8', 'ignore')
    videos2 = re.findall(r'href=["\'](/en/video/\d+/)["\']', html2)
    print('huangguodrama.ai videos:', list(dict.fromkeys(videos2))[:15])
except Exception as e:
    print('huangguodrama.ai err:', e)
