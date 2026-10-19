#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReelShort 短剧批量解析与全集下载工具
功能特性:
  1. 逆向解密 ReelShort 专有 play_info (AES-CBC + 双重Base64 + Inflate) 提取未加密 1080P/720P 高清 HLS 流。
  2. 自动拉取全剧集列表、海报封面、剧目简介及详细元数据。
  3. 支持断点续传（自动跳过已下载集数）、多线程切片并发下载及无损转封装为 MP4。
  4. 支持指定剧目链接/ID 下载，或自动下载最新上线的 N 部短剧。

使用方式:
  python download_reelshort.py --latest 2
  python download_reelshort.py https://www.reelshort.com/movie/6ab8a43a2cdfd334da0580eb
  python download_reelshort.py 6ab8a43a2cdfd334da0580eb
"""

import sys
import os
import re
import json
import time
import base64
import zlib
import argparse
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from Crypto.Cipher import AES
import imageio_ffmpeg

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
UA ="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REFERER = "https://www.reelshort.com/"

# ReelShort 平台内部密钥
AES_KEY = b"VvRSNGFynLBW7aCP"
AES_IV = b"gLn8sxqpzyNjehDP"

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()

def is_image_bytes(data):
    """按文件头判断是否真的是图片 (JPEG / PNG / WEBP / GIF)。"""
    return bool(data) and (
        data[:3] == b"\xff\xd8\xff"
        or data[:8] == b"\x89PNG\r\n\x1a\n"
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
        or data[:4] == b"GIF8"
    )

def is_image_file(path):
    try:
        with open(path, "rb") as f:
            return is_image_bytes(f.read(16))
    except OSError:
        return False

def episode_slug(title):
    """Build the public ReelShort episode URL slug from an English title."""
    return re.sub(r'[^a-z0-9]+', '-', str(title).lower()).strip('-')

def http_get(url, timeout=20, retries=3):
    headers = {"User-Agent": UA, "Referer": REFERER}
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(1 + attempt)

def decrypt_play_info(play_info_str):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    raw = cipher.decrypt(base64.b64decode(play_info_str))
    pad = raw[-1]
    if pad <= 16:
        raw = raw[:-pad]
    step2 = base64.b64decode(raw)
    decompressed = zlib.decompress(step2)
    return json.loads(decompressed.decode("utf-8"))

def get_best_stream(play_info_list):
    h264_streams = [s for s in play_info_list if s.get("Encode") == "H264"]
    if not h264_streams:
        h264_streams = play_info_list
    h264_streams.sort(key=lambda s: s.get("Dpi", 0), reverse=True)
    return h264_streams[0] if h264_streams else None

def get_latest_dramas(limit=2):
    print("正在从 ReelShort 首页获取最新上线的短剧列表...")
    url = "https://www.reelshort.com"
    html = http_get(url).decode("utf-8", "ignore")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if not m:
        raise RuntimeError("未能在 ReelShort 首页提取到 __NEXT_DATA__ 数据！")
    
    data = json.loads(m.group(1))
    info = data["props"]["pageProps"]["fallback"]["/api/ms/hall/webInfo"]
    banners = info.get("banners", [])
    
    drama_candidates = []
    for b in banners:
        jp = b.get("jump_param", {})
        book_id = jp.get("book_id")
        if not book_id:
            continue
        drama_candidates.append(book_id)
        
    print(f"检测到首页推荐/热门剧目共 {len(drama_candidates)} 部，正在比对发布时间...")
    drama_meta = []
    for bid in drama_candidates:
        try:
            meta = get_drama_metadata(bid)
            drama_meta.append(meta)
        except Exception as e:
            print(f"获取剧目 {bid} 信息失败: {e}")
            
    drama_meta.sort(key=lambda x: max(x.get("online_at", 0), x.get("publish_at", 0)), reverse=True)
    selected = drama_meta[:limit]
    
    print("\n=== 最新短剧筛选结果 ===")
    for idx, d in enumerate(selected):
        dt_str = datetime.fromtimestamp(max(d.get("online_at", 0), d.get("publish_at", 0))).strftime('%Y-%m-%d %H:%M')
        print(f"[{idx+1}] 《{d['title']}》 (ID: {d['book_id']}) - 上线时间: {dt_str} - 共 {d['total_episodes']} 集")
    print("========================\n")
    return selected

def get_drama_metadata(book_id_or_url):
    m = re.search(r'(?:movie|full-episodes|book)/([a-zA-Z0-9]+)', str(book_id_or_url))
    book_id = m.group(1) if m else str(book_id_or_url).strip()
    
    movie_url = f"https://www.reelshort.com/movie/{book_id}"
    html = http_get(movie_url).decode("utf-8", "ignore")
    m_data = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if not m_data:
        raise RuntimeError(f"未能解析剧目页面: {movie_url}")
        
    p_data = json.loads(m_data.group(1))["props"]["pageProps"]["data"]
    
    title = p_data.get("book_title", "Unknown")
    desc = p_data.get("special_desc", "")
    pic = p_data.get("book_pic", "")
    online_at = p_data.get("online_at", 0)
    publish_at = p_data.get("publish_at", 0)
    tags = [t.get("tag_name") for t in p_data.get("tag_list", []) if isinstance(t, dict) and t.get("tag_name")]
    if not tags:
        tags = [str(t) for t in p_data.get("tag", []) if t]
    total = p_data.get("total", 0)
    online_base = p_data.get("online_base", [])
    
    return {
        "book_id": book_id,
        "title": title,
        "description": desc,
        "cover_url": pic,
        "online_at": online_at,
        "publish_at": publish_at,
        "total_episodes": total,
        "tags": tags,
        "online_base": online_base,
        "url": movie_url
    }

def fetch_episode_info(book_id, ep_item, title_slug=None):
    ep_num = ep_item.get("serial_number")
    ch_id = ep_item.get("chapter_id")
    embed_url = f"https://www.reelshort.com/embed/{book_id}-{ch_id}"
    
    for attempt in range(3):
        try:
            html = http_get(embed_url, timeout=15).decode("utf-8", "ignore")
            me = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
            if not me:
                continue
            props = json.loads(me.group(1))["props"]["pageProps"]
            # The embed endpoint can silently fall back to episode 1 for locked,
            # missing, or invalid chapter IDs.  Never trust that response for the
            # requested episode or we will save episode 1 under every later name.
            page_ep = props.get("serial_number")
            page_ch = props.get("chapter_id")
            if str(page_ep) != str(ep_num) or page_ch != ch_id:
                # ReelShort's embed route falls back to episode 1 for paid
                # chapters. The public episode page still exposes the correct
                # SD HLS URL, so use it instead of saving episode 1 repeatedly.
                if title_slug:
                    canonical_url = (f"https://www.reelshort.com/episodes/episode-{ep_num}-"
                                     f"{title_slug}-{book_id}-{ch_id}")
                    canonical_html = http_get(canonical_url, timeout=15).decode("utf-8", "ignore")
                    canonical_data = re.search(
                        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                        canonical_html)
                    if canonical_data:
                        canonical_props = json.loads(canonical_data.group(1))["props"]["pageProps"]
                        chapter = canonical_props.get("data") or {}
                        if (str(chapter.get("serial_number")) == str(ep_num)
                                and chapter.get("chapter_id") == ch_id
                                and chapter.get("video_url")):
                            return {
                                "episode": ep_num,
                                "chapter_id": ch_id,
                                "duration": chapter.get("duration", 0),
                                "stream": {"Dpi": 0, "Encode": "H264"},
                                "m3u8_url": chapter["video_url"],
                                "dpi": 0,
                            }
                print(f"  [跳过错误流] 第{ep_num:02d}集请求 {ch_id}，服务端返回第{page_ep}集 {page_ch}")
                return None
            play_info_raw = props.get("play_info")
            if not play_info_raw:
                return None
            stream_list = decrypt_play_info(play_info_raw)
            best_stream = get_best_stream(stream_list)
            return {
                "episode": ep_num,
                "chapter_id": ch_id,
                "duration": props.get("duration", 0),
                "stream": best_stream,
                "m3u8_url": best_stream["PlayURL"] if best_stream else None,
                "dpi": best_stream.get("Dpi") if best_stream else 0
            }
        except Exception:
            time.sleep(1)
    return None

def download_m3u8_video(m3u8_url, out_mp4, desc=""):
    if os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 1024 * 1024:
        print(f"  [跳过已存在] {desc} ({os.path.getsize(out_mp4) / (1024*1024):.2f} MB)")
        return True

    try:
        m3u8_content = http_get(m3u8_url, timeout=15).decode("utf-8", "ignore")
    except Exception as e:
        print(f"  [下载失败] {desc}: 获取 M3U8 失败 ({e})")
        return False

    segments = []
    for line in m3u8_content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            segments.append(urllib.parse.urljoin(m3u8_url, line))

    if not segments:
        print(f"  [下载失败] {desc}: M3U8 未包含分片")
        return False
    if segments[0].split("?")[0].lower().endswith(".m3u8"):
        print(f"  [下载失败] {desc}: 拿到的是主播放列表(嵌套 M3U8)，当前不支持")
        return False

    temp_ts = out_mp4 + ".temp.ts"
    # 先写临时 mp4，成功后再原子改名；否则中断留下的半截文件会被“已存在”检查当成完整文件
    temp_mp4 = out_mp4 + ".temp.mp4"
    ts_chunks = {}

    def fetch_chunk(idx, url):
        data = http_get(url, timeout=25, retries=3)
        return idx, data

    def cleanup():
        for p in (temp_ts, temp_mp4):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(fetch_chunk, i, u): i for i, u in enumerate(segments)}
            for f in as_completed(futures):
                idx, data = f.result()
                ts_chunks[idx] = data
    except Exception as e:
        print(f"  [下载失败] {desc}: 切片下载出错 ({e})")
        return False

    try:
        with open(temp_ts, "wb") as f_out:
            for i in range(len(segments)):
                f_out.write(ts_chunks[i])
        ts_chunks.clear()

        cmd = [
            FFMPEG_EXE,
            "-hide_banner", "-loglevel", "error", "-nostdin",
            "-y",
            "-i", temp_ts,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-movflags", "+faststart",
            "-f", "mp4",
            temp_mp4
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        if res.returncode != 0 or not os.path.exists(temp_mp4) or os.path.getsize(temp_mp4) < 100 * 1024:
            print(f"  [封装失败] {desc}: FFmpeg 转封装错误 {res.stderr.decode('utf-8', 'ignore')[:120]}")
            cleanup()
            return False
        os.replace(temp_mp4, out_mp4)
    except Exception as e:
        print(f"  [封装失败] {desc}: {e}")
        cleanup()
        return False
    finally:
        if os.path.exists(temp_ts):
            try:
                os.remove(temp_ts)
            except OSError:
                pass

    size_mb = os.path.getsize(out_mp4) / (1024 * 1024)
    print(f"  [下载完成] {desc} ({size_mb:.2f} MB)")
    return True

def download_drama(meta, out_base_dir, max_episodes=None):
    safe_title = sanitize_filename(meta["title"])
    drama_dir = os.path.join(out_base_dir, safe_title)
    os.makedirs(drama_dir, exist_ok=True)
    
    print("=" * 65)
    print(f"开始处理剧目: 《{meta['title']}》")
    print(f"剧目 ID: {meta['book_id']}")
    print(f"标签: {', '.join(str(t) for t in meta.get('tags', []) if t)}")
    print(f"总集数: {meta['total_episodes']}")
    print(f"保存路径: {drama_dir}")
    print("=" * 65)
    
    # 1. 保存元数据
    with open(os.path.join(drama_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        
    # 2. 下载高清封面
    if meta.get("cover_url"):
        poster_path = os.path.join(drama_dir, "poster.jpg")
        # 图片 CDN 偶尔会返回反爬 JS 挑战页(HTML)，必须校验内容，否则会把网页当成海报存下来
        if not is_image_file(poster_path):
            try:
                poster_data = http_get(meta["cover_url"])
                if is_image_bytes(poster_data):
                    with open(poster_path, "wb") as f:
                        f.write(poster_data)
                    print("海报封面已下载: poster.jpg")
                else:
                    print("海报下载失败: CDN 返回的不是图片 (可能触发了反爬)，已跳过，下次运行会重试")
            except Exception as e:
                print(f"海报下载失败: {e}")

    # 3. 解析全部剧集流媒体
    online_base = meta.get("online_base", [])
    if max_episodes:
        online_base = online_base[:max_episodes]
        
    total_to_download = len(online_base)
    print(f"\n正在并发解析全剧 {total_to_download} 集流媒体播放源与密钥...")
    
    ep_tasks = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        title_slug = episode_slug(meta["title"])
        futures = {pool.submit(fetch_episode_info, meta["book_id"], item, title_slug): item for item in online_base}
        for f in as_completed(futures):
            res = f.result()
            if res:
                ep_tasks.append(res)
                
    ep_tasks.sort(key=lambda x: x["episode"])
    # Two episode IDs resolving to one stream is the same failure mode as the
    # fallback above.  Keep the first valid task and refuse the rest.
    seen_streams = {}
    valid_tasks = []
    for item in ep_tasks:
        stream = item.get("m3u8_url")
        if stream and stream in seen_streams:
            print(f"  [跳过重复流] 第{item['episode']:02d}集与第{seen_streams[stream]:02d}集解析到同一视频流")
            continue
        if stream:
            seen_streams[stream] = item["episode"]
        valid_tasks.append(item)
    ep_tasks = valid_tasks
    print(f"成功解析到 {len(ep_tasks)}/{total_to_download} 集的高清流媒体地址！")
    
    # 4. 逐集多线程并发下载
    print(f"\n--- 开始下载 《{meta['title']}》 视频文件 ---")
    start_time = time.time()
    success_count = 0

    for n, item in enumerate(ep_tasks, 1):
        ep = item["episode"]
        is_last = (ep == meta["total_episodes"])
        save_name = f"第{ep:02d}集(大结局).mp4" if is_last else f"第{ep:02d}集.mp4"
        out_file = os.path.join(drama_dir, save_name)
        desc = f"第{ep:02d}集 [{item['dpi']}P - 时长{item['duration']}秒]"

        ok = download_m3u8_video(item["m3u8_url"], out_file, desc)
        if ok:
            success_count += 1
        print(f"[进度] {n}/{total_to_download}", flush=True)

    elapsed = time.time() - start_time
    missing = total_to_download - success_count
    if missing:
        print(f"\n《{meta['title']}》 下载未完成：缺 {missing} 集，重新运行同一命令可断点续传。")
    else:
        print(f"\n《{meta['title']}》 下载完成！")
    print(f"成功: {success_count}/{total_to_download} 集, 耗时: {elapsed:.1f} 秒\n")
    return missing == 0

def main():
    parser = argparse.ArgumentParser(description="ReelShort 短剧批量解析与下载工具")
    parser.add_argument("target", nargs="?", default=None, help="剧目网址或 Book ID")
    parser.add_argument("--latest", type=int, default=None, help="自动下载最新的 N 部短剧")
    parser.add_argument("--max-eps", type=int, default=None, help="每部剧最大下载集数 (默认全集)")
    args = parser.parse_args()

    downloads = os.environ.get("DL_DOWNLOADS_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
    base_dir = os.path.join(downloads, "Reelshort")
    os.makedirs(base_dir, exist_ok=True)

    results = []
    try:
        if args.target and not args.latest:
            dramas = [get_drama_metadata(args.target)]
        else:
            # --latest N，或默认模式：下载最新的 N(默认 2) 部短剧
            dramas = get_latest_dramas(limit=args.latest or 2)
    except Exception as e:
        print(f"❌ 获取剧目信息失败: {e}")
        sys.exit(1)

    # 单部剧失败不影响后面的剧
    for d in dramas:
        try:
            results.append(download_drama(d, base_dir, max_episodes=args.max_eps))
        except Exception as e:
            print(f"❌ 《{d.get('title', d.get('book_id'))}》 处理异常: {e}")
            results.append(False)

    sys.exit(0 if results and all(results) else 2)

if __name__ == "__main__":
    main()
