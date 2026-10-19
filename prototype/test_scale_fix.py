import subprocess
import imageio_ffmpeg
import os

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
src = r"c:\Projects\下载工具\downloads\黄果短剧\8714_舞蹈系学妹的零接触\第01集.mp4"
dst = r"c:\Projects\下载工具\prototype\test_fixed.mp4"

# Even simpler: probe width and height in python!
cmd_probe = [ffmpeg, "-i", src]
res = subprocess.run(cmd_probe, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
w, h = 720, 1280
for line in res.stderr.splitlines():
    if "Stream #0:0" in line and "Video:" in line:
        import re
        m = re.search(r", (\d{3,4})x(\d{3,4})", line)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            break

print(f"Original size: {w}x{h}")
if w > h:
    # Horizontal: max height 720
    target_h = min(720, h)
    vf = f"scale=-2:{target_h}"
else:
    # Vertical: max width 720
    target_w = min(720, w)
    vf = f"scale={target_w}:-2"

print(f"Scale filter: {vf}")
cmd = [
    ffmpeg, "-y",
    "-i", src,
    "-vf", vf,
    "-c:v", "libx264",
    "-crf", "24",
    "-preset", "fast",
    "-c:a", "aac",
    "-b:a", "96k",
    dst
]
res2 = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
print("Returncode:", res2.returncode)
if res2.returncode == 0:
    print("Success! Size:", os.path.getsize(dst) / (1024*1024), "MB")
else:
    print(res2.stderr[-300:])
