import urllib.request
import re
import json

url = "https://huangguodrama.ai/en/video/30841/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", "ignore")
        print("Status:", resp.status)
        title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        print("Title:", title.group(1) if title else "None")
        
        # Check __NEXT_DATA__
        next_data = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if next_data:
            data = json.loads(next_data.group(1))
            props = data.get("props", {})
            page_props = props.get("pageProps", {})
            print("pageProps keys:", list(page_props.keys()))
            video = page_props.get("video") or page_props.get("drama") or page_props.get("album")
            if video:
                print("Video/Drama info:", {k: video[k] for k in video if k in ["id", "title", "name", "episodes", "episodeCount", "intro", "tags"]})
            episodes = page_props.get("episodes") or []
            print(f"Episodes count: {len(episodes)}")
            if episodes:
                print("First episode sample:", episodes[0])
            # Check other keys
            for k in page_props:
                if k not in ["video", "episodes"]:
                    val = page_props[k]
                    if isinstance(val, (dict, list)):
                        print(f"Key {k} (type {type(val)}): len {len(val)}")
                    else:
                        print(f"Key {k}: {val}")
        else:
            print("No __NEXT_DATA__ found")
            # Look for scripts or text
            scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
            for s in scripts:
                if "30841" in s or "epPlaySrcs" in s or "m3u8" in s:
                    print("Found relevant script:", s[:300])
except Exception as e:
    print("Error:", e)
