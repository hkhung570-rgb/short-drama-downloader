#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄果短剧全集多线程下载工具
支持解析指定短剧页面，自动获取全部剧集、海报、简介，
并发下载并解密 AES-128 HLS 分片，无损转封装为 MP4。

使用方法:
    python download_huangguo_video.py https://nv5et.wrjmtnebd.cc/video/5860/
"""

import sys
import os
import re
import json
import time
import subprocess
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from Crypto.Cipher import AES
import imageio_ffmpeg

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

def http_get(url, referer=None, retries=5, timeout=20):
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(1 + i * 0.5)

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()

def parse_m3u8(m3u8_content, m3u8_url):
    lines = m3u8_content.decode('utf-8', 'ignore').splitlines()
    key_url = None
    iv = None
    segments = []
    
    seq = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            seq = int(line.split(":")[1])
        elif line.startswith("#EXT-X-KEY:"):
            m_uri = re.search(r'URI=["\'](.*?)["\']', line)
            if m_uri:
                key_url = urllib.parse.urljoin(m3u8_url, m_uri.group(1))
            m_iv = re.search(r'IV=(0x[0-9a-fA-F]+)', line)
            if m_iv:
                iv_str = m_iv.group(1)[2:]
                iv = bytes.fromhex(iv_str.zfill(32))
        elif not line.startswith("#"):
            seg_url = urllib.parse.urljoin(m3u8_url, line)
            segments.append((seq, seg_url))
            seq += 1
            
    return key_url, iv, segments

def download_and_decrypt_segment(seg_info, key, default_iv, referer):
    seq, seg_url = seg_info
    data = http_get(seg_url, referer=referer)
    if key:
        iv = default_iv if default_iv else seq.to_bytes(16, 'big')
        cipher = AES.new(key, AES.MODE_CBC, iv)
        data = cipher.decrypt(data)
    return seq, data

def download_episode(ep_num, total_eps, m3u8_url, out_mp4, referer):
    if os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 1024 * 1024:
        print(f"[{ep_num:02d}/{total_eps:02d}] 已存在，跳过: {os.path.basename(out_mp4)}")
        return True

    print(f"[{ep_num:02d}/{total_eps:02d}] 正在解析 m3u8: {m3u8_url}")
    m3u8_bytes = http_get(m3u8_url, referer=referer)
    key_url, iv, segments = parse_m3u8(m3u8_bytes, m3u8_url)
    
    key = None
    if key_url:
        key = http_get(key_url, referer=referer)
        
    print(f"[{ep_num:02d}/{total_eps:02d}] 共 {len(segments)} 个分片，开始并行下载与解密...")
    
    ts_temp = out_mp4 + ".temp.ts"
    results = {}
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {
            executor.submit(download_and_decrypt_segment, seg, key, iv, referer): seg[0]
            for seg in segments
        }
        for future in as_completed(futures):
            seq, data = future.result()
            results[seq] = data

    with open(ts_temp, "wb") as f_out:
        for seq, _ in segments:
            f_out.write(results[seq])
            
    print(f"[{ep_num:02d}/{total_eps:02d}] 正在无损转封装为 MP4...")
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", ts_temp,
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc",
        "-movflags", "+faststart",
        out_mp4
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        cmd_fallback = [
            FFMPEG_EXE,
            "-y",
            "-i", ts_temp,
            "-c", "copy",
            out_mp4
        ]
        res_fb = subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res_fb.returncode != 0:
            os.rename(ts_temp, out_mp4)
            return True

    if os.path.exists(ts_temp):
        os.remove(ts_temp)
        
    size_mb = os.path.getsize(out_mp4) / (1024 * 1024)
    print(f"[{ep_num:02d}/{total_eps:02d}] 完成: {os.path.basename(out_mp4)} ({size_mb:.2f} MB)")
    return True

def fetch_page_initial_data(url):
    html = http_get(url).decode('utf-8', 'ignore')
    m = re.search(r'<script id="videoInitialData" type="application/json">(.*?)</script>', html)
    if not m:
        return None, html
    return json.loads(m.group(1)), html

def download_drama(page_url):
    print("=" * 60)
    print(f"开始解析短剧页面: {page_url}")
    print("=" * 60)
    
    parsed = urllib.parse.urlparse(page_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    
    init_data, html = fetch_page_initial_data(page_url)
    if not init_data:
        print("错误: 未能在页面中找到 videoInitialData 数据！")
        return
        
    drama_id = init_data.get("id") or "drama"
    drama_title = sanitize_filename(init_data.get("title", f"drama_{drama_id}"))
    description = init_data.get("description", "")
    cover_src = init_data.get("coverSrc") or init_data.get("posterSrc")
    tags = init_data.get("tags", [])
    
    # 提取所有剧集连接
    # 形如: <a class="...hg-web-play__ep..." href="/video/5860/ep-2/" data-ep-id="2">
    ep_matches = re.findall(r'<a [^>]*class="[^"]*hg-web-play__ep[^"]*"[^>]*href="([^"]*)"[^>]*data-ep-id="(\d+)"', html)
    
    ep_dict = {}
    for href, ep_id in ep_matches:
        ep_dict[int(ep_id)] = urllib.parse.urljoin(origin, href)
        
    if not ep_dict:
        # 如果没有列表，至少当前页是第1集
        ep_dict[1] = page_url
        
    total_eps = len(ep_dict)
    
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads", "黄果短剧", f"{drama_id}_{drama_title}")
    os.makedirs(out_dir, exist_ok=True)
    
    print(f"剧名: {drama_title}")
    print(f"编号: {drama_id}")
    print(f"标签: {', '.join(tags)}")
    print(f"总集数: {total_eps}")
    print(f"保存路径: {out_dir}")
    print(f"简介: {description}\n")
    
    # 保存元数据
    metadata = {
        "id": drama_id,
        "title": drama_title,
        "description": description,
        "tags": tags,
        "total_episodes": total_eps,
        "source_url": page_url,
        "cover_url": cover_src
    }
    with open(os.path.join(out_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
        
    # 保存海报
    if cover_src:
        poster_path = os.path.join(out_dir, "poster.jpg")
        if not os.path.exists(poster_path):
            try:
                print("正在下载海报封面...")
                poster_bytes = http_get(cover_src, referer=origin)
                with open(poster_path, "wb") as f:
                    f.write(poster_bytes)
                print(f"海报封面已保存: poster.jpg\n")
            except Exception as e:
                print(f"海报下载失败: {e}\n")
                
    # 逐集下载
    for ep_num in sorted(ep_dict.keys()):
        ep_url = ep_dict[ep_num]
        save_name = f"第{ep_num:02d}集(大结局).mp4" if ep_num == total_eps else f"第{ep_num:02d}集.mp4"
        out_mp4 = os.path.join(out_dir, save_name)
        
        if os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 1024 * 1024:
            print(f"[{ep_num:02d}/{total_eps:02d}] 已存在，跳过: {save_name}")
            continue
            
        # 获取当前集的 videoSrc
        if ep_num == 1 and init_data.get("videoSrc"):
            m3u8_url = init_data.get("videoSrc")
        else:
            print(f"[{ep_num:02d}/{total_eps:02d}] 正在提取第 {ep_num} 集播放源: {ep_url}")
            ep_data, _ = fetch_page_initial_data(ep_url)
            if not ep_data or not ep_data.get("videoSrc"):
                print(f"[{ep_num:02d}/{total_eps:02d}] 未能提取到播放地址，跳过！")
                continue
            m3u8_url = ep_data.get("videoSrc")
            
        download_episode(ep_num, total_eps, m3u8_url, out_mp4, origin)

    print("\n" + "=" * 60)
    print(f"全部下载任务完成！保存目录: {out_dir}")
    print("=" * 60)

if __name__ == "__main__":
    urls = sys.argv[1:] if len(sys.argv) > 1 else ["https://nv5et.wrjmtnebd.cc/video/5860/"]
    for idx, u in enumerate(urls, 1):
        print(f"\n>>>>>>>> 开始下载第 [{idx}/{len(urls)}] 部短剧 <<<<<<<<")
        try:
            download_drama(u)
        except Exception as err:
            print(f"下载失败 {u}: {err}")
