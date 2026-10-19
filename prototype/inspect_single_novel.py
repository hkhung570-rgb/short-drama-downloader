import urllib.request
import urllib.parse
import re
import json

url = "https://huangguodrama.ai/en/novels/%E4%B8%8A%E6%B5%B7%E8%BE%A3%E5%A6%88/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", "ignore")
        print("Status:", resp.status)
        title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        print("Title:", title.group(1) if title else "None")
        
        # Check text length / body
        clean_text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.S)
        clean_text = re.sub(r'<style[^>]*>.*?</style>', ' ', clean_text, flags=re.S)
        clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
        words = clean_text.split()
        print("Clean text word count:", len(words))
        print("Text snippet:", ' '.join(words[:150]))
        
        # Check images / audio / media
        imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html)
        print("Images:", set(imgs))
        media = re.findall(r'https?://[^\s"\'\\<>]+\.(?:mp3|mp4|m3u8|wav|jpg|png|webp)', html)
        print("Media URLs count:", len(media))
        for m in set(media):
            if not m.endswith(('.png', '.svg', '.ico')):
                print("  Media:", m)
                
        # Check if chapters or full novel text exists
        # Look for chapters or content in Next.js stream
        pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html)
        full_f = ""
        for p in pushes:
            try:
                s = bytes(p, "utf-8").decode("unicode_escape")
                full_f += s
            except Exception:
                full_f += p
        print("Stream len:", len(full_f))
        # Look for story/novel keys
        for kw in ["content", "chapters", "summary", "character", "characters", "author", "tags"]:
            found = re.findall(rf'(\"{kw}\":[^,\n\}}]+)', full_f[:30000], re.I)
            if found:
                print(f"Key '{kw}':", found[:3])
except Exception as e:
    print("Error:", e)
