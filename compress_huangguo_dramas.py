#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄果短剧全库 720P 视觉无损批量压缩工具（自适应分辨率增强版）
"""

import os
import sys
import time
import re
import subprocess
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
BASE_DIR = r"c:\Projects\下载工具\downloads\黄果短剧"

def get_video_info(fpath):
    cmd = [FFMPEG_EXE, "-i", fpath]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    duration = 0.0
    bitrate = 0.0
    w, h = 720, 1280
    for line in res.stderr.splitlines():
        if "Duration:" in line:
            parts = line.split(",")
            dur_str = parts[0].replace("Duration:", "").strip()
            try:
                parts_time = dur_str.split(":")
                duration = float(parts_time[0])*3600 + float(parts_time[1])*60 + float(parts_time[2])
            except Exception:
                pass
            for p in parts:
                if "bitrate:" in p:
                    try:
                        br_str = p.replace("bitrate:", "").replace("kb/s", "").strip()
                        bitrate = float(br_str)
                    except Exception:
                        pass
        if "Stream #0:0" in line and "Video:" in line:
            m = re.search(r", (\d{3,4})x(\d{3,4})", line)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
                
    return duration, bitrate, w, h

def display_size(path):
    """读取视频的显示宽高（按 SAR 和旋转标记换算），读取失败返回 None。"""
    import re
    out = subprocess.run([FFMPEG_EXE, "-hide_banner", "-i", path], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).stderr.decode("utf-8", "ignore")
    v = re.search(r"Video: .*?, (\d{2,5})x(\d{2,5})([^\n]*)", out)
    if not v:
        return None
    w, h = int(v.group(1)), int(v.group(2))
    sar = re.search(r"SAR (\d+):(\d+)", v.group(3))
    if sar and int(sar.group(2)) and abs(int(sar.group(1)) / int(sar.group(2)) - 1) > 0.005:
        w = round(w * int(sar.group(1)) / int(sar.group(2)))
    rot = re.search(r"rotation of (-?[\d.]+) degrees", out) or re.search(r"rotate\s*:\s*(-?\d+)", out)
    if rot and round(abs(float(rot.group(1))) / 90) % 2 == 1:
        w, h = h, w
    return w, h


def aspect_preserved(src_path, out_path, tol=0.005):
    """压缩后的显示宽高比必须和原片一致（容差 0.5%，偶数对齐最多产生 ~0.2%）。返回 (是否一致, 说明)。"""
    a, b = display_size(src_path), display_size(out_path)
    if not a or not b:
        return False, "无法读取宽高，不能确认比例"
    gap = abs((a[0] / a[1]) / (b[0] / b[1]) - 1)
    return gap <= tol, f"原片 {a[0]}x{a[1]} -> 压缩后 {b[0]}x{b[1]}（偏差 {gap:.2%}）"


def verify_mp4(fpath):
    if not os.path.exists(fpath) or os.path.getsize(fpath) < 500 * 1024:
        return False
    cmd = [FFMPEG_EXE, "-v", "error", "-i", fpath, "-f", "null", "-"]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    return res.returncode == 0

def compress_single(src_path):
    orig_bytes = os.path.getsize(src_path)
    orig_mb = orig_bytes / (1024 * 1024)
    
    dur, bitrate, w, h = get_video_info(src_path)
    # 如果码率已经很低（<= 1450 kbps），说明已经是压缩版或超轻量，跳过
    if bitrate > 0 and bitrate <= 1450:
        print(f"  [跳过] 码率已低于 1450 kbps ({bitrate:.0f} kbps): {os.path.basename(src_path)}")
        return False, 0
        
    temp_dst = src_path + ".compressed.mp4"
    if os.path.exists(temp_dst):
        os.remove(temp_dst)
        
    if w > h:
        vf = f"scale=-2:{min(720, h)}"
    else:
        vf = f"scale={min(720, w)}:-2"
        
    print(f"  [正在压制] {os.path.basename(src_path)} (原大小: {orig_mb:.2f} MB, {w}x{h}, 码率: {bitrate:.0f} kbps, 时长: {int(dur//60)}分{int(dur%60)}秒)...")
    
    t0 = time.time()
    cmd = [
        FFMPEG_EXE, "-y",
        "-i", src_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-crf", "24",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "96k",
        "-movflags", "+faststart",
        temp_dst
    ]
    
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    elapsed = time.time() - t0
    
    if res.returncode != 0:
        print(f"  [失败] FFmpeg 编码失败: {os.path.basename(src_path)}")
        if os.path.exists(temp_dst):
            os.remove(temp_dst)
        return False, 0
        
    # 验证新文件完整性
    print(f"  [验证中] 正在校验压制后视频完整性...")
    if not verify_mp4(temp_dst):
        print(f"  [警告] 视频完整性校验未通过，保留原文件！")
        if os.path.exists(temp_dst):
            os.remove(temp_dst)
        return False, 0
        
    ok, detail = aspect_preserved(src_path, temp_dst)
    if not ok:
        print(f"  [警告] 宽高比校验未通过，保留原文件！{detail}")
        os.remove(temp_dst)
        return False, 0

    new_bytes = os.path.getsize(temp_dst)
    new_mb = new_bytes / (1024 * 1024)
    saved_mb = orig_mb - new_mb
    ratio = (1 - new_mb / orig_mb) * 100
    
    # 验证成功，删除原下载文件，重命名替换
    os.remove(src_path)
    os.rename(temp_dst, src_path)
    
    print(f"  [成功] 已替换并删除原片: {orig_mb:.2f} MB -> {new_mb:.2f} MB (节省 {saved_mb:.2f} MB, 缩减 {ratio:.1f}%, 耗时 {elapsed:.1f}s)\n")
    return True, saved_mb

def main():
    print("=" * 65)
    print("      黄果短剧全库 720P 视觉无损顺序压缩与空间释放程序 (增强版)")
    print("=" * 65)
    
    target_folders = [
        "7628_时停手表",
        "8545_俏黄蓉之襄阳九阴真茎",
        "8714_舞蹈系学妹的零接触",
        "4466_母子同欢"
    ]
    
    all_tasks = []
    for tf in target_folders:
        dirpath = os.path.join(BASE_DIR, tf)
        if not os.path.exists(dirpath):
            continue
        for f in sorted(os.listdir(dirpath)):
            if f.endswith(".mp4") and not f.endswith(".compressed.mp4"):
                all_tasks.append(os.path.join(dirpath, f))
                
    total_files = len(all_tasks)
    print(f"待处理任务: {total_files} 个 MP4 分集。开始顺序压制...\n")
    
    compressed_count = 0
    total_saved_mb = 0.0
    
    for idx, fpath in enumerate(all_tasks, 1):
        rel_path = os.path.relpath(fpath, BASE_DIR)
        print(f"[{idx:02d}/{total_files:02d}] 检查: {rel_path}")
        success, saved = compress_single(fpath)
        if success:
            compressed_count += 1
            total_saved_mb += saved
            
    print("=" * 65)
    print(f"本轮压制流程完成！")
    print(f"成功压缩剧集: {compressed_count} 集")
    print(f"累计释放磁盘空间: {total_saved_mb:.2f} MB ({total_saved_mb/1024:.2f} GB)")
    print("=" * 65)

if __name__ == "__main__":
    main()
