import urllib.request
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Referer": "https://www.reelshort.com/"
}

def post(url, data={}):
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:
        return {"error": str(e)}

def get(url):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:
        return {"error": str(e)}

print("Testing webNewReleaseBooks (GET):", get("https://www.reelshort.com/api/ms/hall/webNewReleaseBooks"))
print("Testing webNewReleaseBooks (POST):", post("https://www.reelshort.com/api/ms/hall/webNewReleaseBooks", {"page": 1, "pageSize": 10}))
