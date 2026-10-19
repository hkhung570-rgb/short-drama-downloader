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

def decrypt_response(encrypted_str):
    if not encrypted_str or not isinstance(encrypted_str, str):
        return {}
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    try:
        raw_decrypted = cipher.decrypt(base64.b64decode(encrypted_str))
        pad_len = raw_decrypted[-1]
        if pad_len <= 16:
            raw_decrypted = raw_decrypted[:-pad_len]
        
        # In JS:
        # i = I(I(o)) where o = r.toString(Base64)
        # raw_decrypted is decoded binary string of base64
        compressed_bytes = base64.b64decode(raw_decrypted.decode('latin1'))
        decompressed = zlib.decompress(compressed_bytes, -zlib.MAX_WBITS)
        return json.loads(decompressed.decode('utf-8'))
    except Exception as e1:
        try:
            compressed_bytes = base64.b64decode(raw_decrypted.decode('latin1'))
            decompressed = zlib.decompress(compressed_bytes)
            return json.loads(decompressed.decode('utf-8'))
        except Exception as e2:
            return {"err1": str(e1), "err2": str(e2), "raw": raw_decrypted[:100].hex()}

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
            resp_body = resp.read().decode("utf-8", "ignore")
            res_json = json.loads(resp_body)
            if isinstance(res_json, dict) and "data" in res_json and isinstance(res_json["data"], str):
                res_json["decrypted_data"] = decrypt_response(res_json["data"])
            return res_json
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "ignore")
        return {"code": e.code, "msg": str(e), "body": err_body}
    except Exception as e:
        return {"error": str(e)}

book_id = "6aafa7fc530d47585a054f74"
print("Testing /api/video/book/getChapterList for:", book_id)
res = api_request("/api/video/book/getChapterList", {"book_id": book_id})
print("Result keys:", list(res.keys()) if isinstance(res, dict) else type(res))
if "decrypted_data" in res:
    print("Decrypted keys:", list(res["decrypted_data"].keys()) if isinstance(res["decrypted_data"], dict) else type(res["decrypted_data"]))
    print("Decrypted sample:", str(res["decrypted_data"])[:500])
else:
    print("Result:", str(res)[:500])
