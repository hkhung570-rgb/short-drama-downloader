#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄果短剧单剧下载工具
支持解析指定剧集页面并下载全部剧集 MP4 视频与海报封面。
示例:
  python download_drama.py https://huangguodrama.ai/en/video/30841/
"""

import sys
import os
import re
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0"

def fetch_html(url):
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception as e:
            if attempt == 4:
                raise
            time.sleep(2)

def extract_drama_info(page_url):
    html = fetch_html(page_url)
    
    # 提取标题
    title_m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    raw_title = title_m.group(1).strip() if title_m else "Drama"
    drama_title = raw_title.split("Episode")[0].split("–")[0].split("|")[0].strip()
    
    # 提取剧集 ID
    id_m = re.search(r'/(?:video|detail)/(\d+)/', page_url)
    drama_id = id_m.group(1) if id_m else "unknown"

    # 提取所有剧集
    ep_pattern = re.compile(
        r'\{\\"n\\":(\d+),\\"title\\":\\"(.*?)\\",\\"desc\\":\\"(.*?)\\",\\"cover\\":\\"(.*?)\\",\\"video\\":\\"(.*?)\\"\}'
    )
    
    episodes = []
    seen_eps = set()
    for m in ep_pattern.finditer(html):
        n = int(m.group(1))
        if n in seen_eps:
            continue
        seen_eps.add(n)
        
        ep_title = m.group(2).encode().decode('unicode_escape', 'ignore')
        ep_desc = m.group(3).encode().decode('unicode_escape', 'ignore')
        ep_cover = m.group(4).encode().decode('unicode_escape', 'ignore')
        ep_video = m.group(5).encode().decode('unicode_escape', 'ignore')
        
        # 补全相对路径
        if ep_video.startswith("/"):
            ep_video = urllib.parse.urljoin("https://huangguodrama.ai", ep_video)
        if ep_cover.startswith("/"):
            ep_cover = urllib.parse.urljoin("https://huangguodrama.ai", ep_cover)
            
        episodes.append({
            "n": n,
            "title": ep_title,
            "desc": ep_desc,
            "cover": ep_cover,
            "video": ep_video
        })

    episodes.sort(key=lambda x: x["n"])
    return {
        "drama_id": drama_id,
        "title": drama_title,
        "url": page_url,
        "episodes": episodes
    }

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()

def download_file(url, out_path, desc=""):
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        # Check size if available
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=10) as r:
                cl = int(r.headers.get("content-length", 0))
                if cl > 0 and os.path.getsize(out_path) == cl:
                    print(f"  [跳过已存在] {desc} ({cl / (1024*1024):.2f} MB)")
                    return True
        except Exception:
            pass

    tmp_path = out_path + ".tmp"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r, open(tmp_path, "wb") as f:
                cl = int(r.headers.get("content-length", 0))
                downloaded = 0
                block_size = 64 * 1024
                while True:
                    chunk = r.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                
            os.replace(tmp_path, out_path)
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            print(f"  [下载完成] {desc} ({size_mb:.2f} MB)")
            return True
        except Exception as e:
            print(f"  [重试 {attempt+1}/3] {desc} 失败: {e}")
            time.sleep(2)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    return False

def main():
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://huangguodrama.ai/en/video/30841/"
    print(f"=== 开始解析剧集: {target_url} ===")
    info = extract_drama_info(target_url)
    
    clean_title = sanitize_filename(info["title"])
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads", f"{info['drama_id']}_{clean_title}")
    os.makedirs(out_dir, exist_ok=True)
    
    print(f"剧名: {info['title']}")
    print(f"解析到可下载集数: {len(info['episodes'])} 集")
    print(f"输出目录: {out_dir}\n")

    # 保存元数据
    with open(os.path.join(out_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    # 下载海报封面
    if info["episodes"] and info["episodes"][0].get("cover"):
        cover_url = info["episodes"][0]["cover"]
        download_file(cover_url, os.path.join(out_dir, "poster.jpg"), desc="剧集海报")

    # 批量下载所有集视频
    print(f"\n--- 开始下载全部 {len(info['episodes'])} 集视频 ---")
    start_time = time.time()
    
    tasks = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for ep in info["episodes"]:
            safe_ep_title = sanitize_filename(ep['title'])
            fn = f"EP{ep['n']:02d} - {safe_ep_title}.mp4"
            out_file = os.path.join(out_dir, fn)
            desc = f"EP{ep['n']:02d} {ep['title']}"
            tasks.append(pool.submit(download_file, ep["video"], out_file, desc))

    results = [t.result() for t in tasks]
    success_count = sum(1 for r in results if r)
    elapsed = time.time() - start_time
    
    print(f"\n=== 全部任务结束 ===")
    print(f"成功: {success_count}/{len(info['episodes'])} 集")
    print(f"耗时: {elapsed:.1f} 秒")
    print(f"保存路径: {out_dir}")

if __name__ == "__main__":
    main()
