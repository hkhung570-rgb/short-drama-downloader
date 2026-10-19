import urllib.request
import re
import json

url = "https://huangguodrama.ai/en/novels/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", "ignore")
        print("Status:", resp.status)
        title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        print("Title:", title.group(1) if title else "None")
        
        # Look for links to novel details
        links = re.findall(r'href=["\']([^"\']+)["\']', html)
        novel_links = [l for l in set(links) if "novel" in l or "story" in l or "book" in l]
        print(f"Novel related links ({len(novel_links)}):")
        for l in sorted(novel_links)[:30]:
            print("  ", l)

        # Check Next.js stream
        pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html)
        full_f = ""
        for p in pushes:
            try:
                s = bytes(p, "utf-8").decode("unicode_escape")
                full_f += s
            except Exception:
                full_f += p
        print("Next stream len:", len(full_f))
        
        # Check if list of novels exists in stream
        for kw in ["novels", "stories", "books", "items", "catalog", "list"]:
            m = re.findall(rf'(\"{kw}\":\s*\[.*?\])', full_f[:50000])
            if m:
                print(f"Stream keyword '{kw}': count {len(m)}, first len {len(m[0])}")
                print(m[0][:300])

except Exception as e:
    print("Error:", e)
