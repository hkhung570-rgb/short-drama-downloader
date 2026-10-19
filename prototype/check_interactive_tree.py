import urllib.request
import re
import json

url = "https://huangguodrama.ai/en/interactive/hehuan-sect/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")

# Find nodes or story json
# Let's search for "story":{...} or "nodes":{...}
m = re.search(r'\\"story\\":(\{.*?\})\s*,\s*\\"nodes\\":(\{.*?\})\s*,\s*\\"(?:endings|routes|meta|initial)', html)
if not m:
    # try broader search
    m = re.search(r'\"story\":(\{.*?\}),\s*\"nodes\":(\{.*?\})', html)

# Let's extract all nodes from the Next.js stream
pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html)
full_f = ""
for p in pushes:
    try:
        s = bytes(p, "utf-8").decode("unicode_escape")
        full_f += s
    except Exception:
        full_f += p

# In full_f, look for nodes
nodes_idx = full_f.find('"nodes":{')
if nodes_idx != -1:
    print("Found nodes in stream!")
    chunk = full_f[nodes_idx+8:]
    # balance braces to extract nodes dict
    depth = 0
    end_idx = 0
    for i, c in enumerate(chunk):
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break
    nodes_json = chunk[:end_idx]
    try:
        nodes = json.loads(nodes_json)
        print(f"Parsed {len(nodes)} interactive nodes:")
        for k, v in nodes.items():
            print(f"  [{k}] title: {v.get('title')} | video: {v.get('video')} | choices: {len(v.get('choices', []))}")
    except Exception as e:
        print("Nodes JSON parse error:", e)
        print("Raw nodes chunk:", nodes_json[:500])

# Also check sizes of all 19 videos
videos = sorted(list(set(re.findall(r'https?://media\.huangguodrama\.ai/motion/interactive/hehuan-sect/[^\s"\'\\<>]+\.mp4', html))))
print(f"\nFound {len(videos)} unique video branch URLs:")
total_size = 0
for v in videos:
    fn = v.split('/')[-1]
    try:
        r = urllib.request.Request(v, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(r, timeout=10) as resp:
            cl = int(resp.headers.get("content-length", 0))
            total_size += cl
            print(f"  {fn:<30} {cl / (1024*1024):.2f} MB")
    except Exception as e:
        print(f"  {fn:<30} Error: {e}")

print(f"\nTotal size: {total_size / (1024*1024):.2f} MB")
