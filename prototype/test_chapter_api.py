import time
import json
import hmac
import hashlib
import base64
import zlib
import urllib.request
from Crypto.Cipher import AES

AES_KEY = b"VvRSNGFynLBW7aCP"
AES_IV = b"gLn8sxqpzyNjehDP"
SIGN_SECRET = "zj8N6zKEdrK8d1MxwHSvExdgQ868q1yT"

def calc_sign(params, secret=SIGN_SECRET):
    items = []
    for k, v in params.items():
        if v is None or v == "" or v == "null":
            continue
        val_str = json.dumps(v, separators=(',', ':')) if isinstance(v, (dict, list)) else str(v)
        items.append((k, val_str))
    items.sort(key=lambda x: x[0])
    query = "&".join(f"{k}={v}" for k, v in items)
    return hmac.new(secret.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()

def decrypt_data(encrypted_str):
    if not encrypted_str or not isinstance(encrypted_str, str):
        return {}
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    try:
        raw_decrypted = cipher.decrypt(base64.b64decode(encrypted_str))
        pad_len = raw_decrypted[-1]
        if pad_len <= 16:
            raw_decrypted = raw_decrypted[:-pad_len]
        step2 = base64.b64decode(raw_decrypted)
        decompressed = zlib.decompress(step2)
        return json.loads(decompressed.decode('utf-8'))
    except Exception as e:
        return {"err": str(e)}

def api_request(path, data=None):
    if data is None:
        data = {}
    ts = int(time.time())
    dev_id = "reelshortdev" + str(int(time.time() * 1000))
    common_params = {
        "apiVersion": "1.0.4",
        "channelId": "WEB41001",
        "session": "",
        "clientVer": "2.4.00",
        "devId": dev_id,
        "lang": "en",
        "ts": ts,
        "uid": "0"
    }
    
    all_params = {}
    all_params.update(data)
    all_params.update(common_params)
    sign = calc_sign(all_params)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Referer": "https://www.reelshort.com/",
        "sign": sign
    }
    for k, v in common_params.items():
        headers[k] = str(v)
        
    url = "https://www.reelshort.com" + path
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_body = resp.read()
            # Can be json or encrypted string
            try:
                res_json = json.loads(resp_body.decode('utf-8'))
                if "data" in res_json and isinstance(res_json["data"], str):
                    res_json["decrypted"] = decrypt_data(res_json["data"])
                return res_json
            except Exception:
                # Direct encrypted string
                enc_str = resp_body.decode('utf-8', 'ignore').strip()
                return decrypt_data(enc_str)
    except urllib.error.HTTPError as e:
        return {"http_code": e.code, "body": e.read().decode('utf-8', 'ignore')}
    except Exception as e:
        return {"error": str(e)}

book_id = "6aafa7fc530d47585a054f74"
chapter_1 = "aqthox3d16"
chapter_2 = "vxywyv2hus"

print("1. Testing getChapterInfo for chapter 1:")
r1 = api_request("/api/video/book/getChapterInfo", {"book_id": book_id, "chapter_id": chapter_1})
print(json.dumps(r1, indent=2)[:500])

print("\n2. Testing getChapterInfo for chapter 2:")
r2 = api_request("/api/video/book/getChapterInfo", {"book_id": book_id, "chapter_id": chapter_2})
print(json.dumps(r2, indent=2)[:500])

print("\n3. Testing getFreeChapter:")
r3 = api_request("/api/video/book/getFreeChapter", {"book_id": book_id})
print(json.dumps(r3, indent=2)[:500])
