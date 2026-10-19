import base64
import zlib
import json
from Crypto.Cipher import AES

AES_KEY = b"VvRSNGFynLBW7aCP"
AES_IV = b"gLn8sxqpzyNjehDP"

play_info = "PKPXzclgs6V2Wl3Ko6sfGZmmY5uqOEkylCsDqATsyzDugWY8kuSQ05I6vjGw4B6g9LmVUXOv8i7ipy+3BMPaIZAEfDkCxT0+BN8eakWeQOPQjt4pI8M+3MCcXqztsxAtwmc95ahmtbhVB/YD4nEwDNEdUotCKaeTUO1EWfZG7cd3OLsfCPPxFofMCddxVK4X+aOZifFMc/X3yX1HzXQ0o03Am6RXWUPqEOB2qVNxuZWx1fQpTjZp7IKV9SzFhQK5G45Y77rUQqfvcyoMKCHElL56NrbCthqBDSyOcfTNPXDG58RLUWGntke+5LrKkw5bhHD7P/CASELxk63eqpY4v/UO+9YssRXt+9veXwgFnWIkAZycHLmXb9Dt+TEHLHDC9BUm0JyvwXiPMTr5l7R6xSdlP5i0PsnsiJ59buWEku2hio0RSUpr0uNl/T9Dz4YyMjG7YW+/8a4k1/CMCdWY+OuimqIkpqQRXP4RkN2jNXXjDKkbL3aBKGGEpq2+7B+P27LUQ8veALyBYOrtolLey81mgUHgV9M6as3AOMVWLzP4BEJ42vpnZux0MU7X8avPepA0FK2LstU8MNVr93P2t7R4OmM0bdeJIIaO/tzj+AHkvCCNFxCOkNnXQNu5y8w2e6XHspr6hLaymLJZ+yAVpZGsM0SM4ZQn+yTfH3lbObIgYncDBfbK/335jwhVY7jxLwAy+aHRIS6AVkrDzL4BVmn9ArwFHKUmB1DI3yJkU2SP0seGRyHs/xgsVy3XLO7W79QRKabP9k2tLYcXVoGkyg=="

cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
raw = cipher.decrypt(base64.b64decode(play_info))
pad = raw[-1]
if pad <= 16:
    raw = raw[:-pad]
print("Raw decrypted len:", len(raw))
print("Raw decrypted text preview:", raw[:50])

step2 = base64.b64decode(raw)
print("Step2 len:", len(step2))

try:
    decompressed = zlib.decompress(step2)
    print("SUCCESS decompressed!")
    data = json.loads(decompressed.decode("utf-8"))
    print(json.dumps(data, indent=2))
except Exception as e:
    try:
        decompressed = zlib.decompress(step2, -zlib.MAX_WBITS)
        print("SUCCESS decompressed (raw inflate)!")
        data = json.loads(decompressed.decode("utf-8"))
        print(json.dumps(data, indent=2))
    except Exception as e2:
        print("Failed:", e, e2)
