import urllib.request
import re
import json

url = "https://huangguodrama.ai/en/interactive/hehuan-sect/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", "ignore")
        print("Status:", resp.status)
        title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        print("Title:", title.group(1) if title else "None")
        
        # Look for video / m3u8 / mp4
        videos = re.findall(r'https?://[^\s"\'\\<>]+\.(?:m3u8|mp4)[^\s"\'\\<>]*', html)
        print("Videos in HTML:", len(videos))
        for v in set(videos):
            print("  Video:", v)
            
        # Check Next.js App router streams or scripts
        pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html)
        full_f = ""
        for p in pushes:
            try:
                s = bytes(p, "utf-8").decode("unicode_escape")
                full_f += s
            except Exception:
                full_f += p
        print("Next stream len:", len(full_f))
        
        # Look for videos in stream
        stream_videos = re.findall(r'https?://[^\s"\'\\<>]+\.(?:m3u8|mp4)[^\s"\'\\<>]*', full_f)
        print("Videos in stream:", len(stream_videos))
        for v in set(stream_videos):
            print("  Stream Video:", v)

        # Look for interactive nodes / story tree / choices
        # keywords: nodes, choices, scenes, story, branches, interactive
        for kw in ["nodes", "scenes", "branches", "choices", "interactive", "episodes", "steps", "story"]:
            matches = re.findall(rf'(\"{kw}\":[^,\n\}}]+)', full_f, re.I)
            if matches:
                print(f"Keyword '{kw}':", matches[:5])
except Exception as e:
    print("Error:", e)
