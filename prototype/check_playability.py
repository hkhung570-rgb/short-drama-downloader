import urllib.request
import re
import json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def check_drama_playable(vid):
    url = f"https://nv5et.wrjmtnebd.cc/video/{vid}/"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', 'ignore')
    m = re.search(r'<script id="videoInitialData" type="application/json">(.*?)</script>', html)
    if not m:
        return f"{vid}: no data"
    data = json.loads(m.group(1))
    title = data.get("title")
    ep_matches = re.findall(r'<a [^>]*class="[^"]*hg-web-play__ep[^"]*"[^>]*href="([^"]*)"[^>]*data-ep-id="(\d+)"', html)
    if not ep_matches:
        ep_matches = [ (url, 1) ]
    
    playable_eps = 0
    total_eps = len(ep_matches)
    
    # Check ep 1
    if data.get("videoSrc"):
        playable_eps += 1
        
    for href, ep_id in ep_matches[1:]:
        ep_url = f"https://nv5et.wrjmtnebd.cc{href}" if href.startswith('/') else href
        try:
            req_ep = urllib.request.Request(ep_url, headers={"User-Agent": UA})
            html_ep = urllib.request.urlopen(req_ep, timeout=10).read().decode('utf-8', 'ignore')
            m_ep = re.search(r'<script id="videoInitialData" type="application/json">(.*?)</script>', html_ep)
            if m_ep:
                d_ep = json.loads(m_ep.group(1))
                if d_ep.get("videoSrc"):
                    playable_eps += 1
        except Exception as e:
            pass
            
    return f"{vid}: {title} | {playable_eps}/{total_eps} playable"

for vid in ['7628', '8756', '8545', '7811', '8714', '6233']:
    print(check_drama_playable(vid))
