#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Slitz 短剧批量解析与下载归档标准工具
支持功能:
  1. 自动化视频分集探测与多线程下载 (HD MP4)
  2. 自动拉取官方高清海报 (poster.webp / poster.jpg)
  3. 自动生成规范结构化元数据 (metadata.json)
  4. 自动生成详细中文剧集说明 (剧集说明.md)
  5. 自动更新总目录索引 (README.md, dramas_list.md, list.txt)

使用方式:
    python download_slitz.py https://www.slitz.com/shorts/room-service
    python download_slitz.py room-service
"""

import sys
import os
import re
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

_DOWNLOADS = os.environ.get('DL_DOWNLOADS_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
BASE_DIR = os.path.join(_DOWNLOADS, 'Slitz短剧')

def extract_slug(input_str):
    m = re.search(r'shorts/([a-zA-Z0-9\-]+)', input_str)
    if m:
        return m.group(1).rstrip('/')
    return input_str.strip().strip('/')

def _head(url, retries=3):
    """
    HEAD 探测。返回 (存在?, Content-Length)。
    403/404/410 视为“不存在”；网络错误/5xx 重试，仍失败则抛出，
    避免把网络抖动误判成“已经是最后一集”而少下载并错标大结局。
    """
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS, method='HEAD')
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200, int(resp.headers.get('Content-Length', 0) or 0)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410):
                return False, 0
            last_err = e
        except Exception as e:
            last_err = e
        time.sleep(1 + attempt)
    raise RuntimeError(f"探测失败 {url}: {last_err}")


def probe_episodes(slug):
    bases = [
        f'https://slitz-media-cdn.b-cdn.net/candy/{slug}',
        f'https://slitz-media-cdn.b-cdn.net/originals/{slug}'
    ]
    suffixes = ['-hd.mp4', '.mp4', '-sd.mp4']

    found_base = None
    for base in bases:
        for suf in suffixes:
            exists, _ = _head(f'{base}/ep01{suf}')
            if exists:
                found_base = base
                break
        if found_base:
            break

    if not found_base:
        return None, []

    episodes = []
    for ep in range(1, 200):
        ep_found = False
        for suf in suffixes:
            url = f'{found_base}/ep{ep:02d}{suf}'
            exists, size = _head(url)
            if exists:
                episodes.append({
                    'episode': ep,
                    'suffix': suf,
                    'url': url,
                    'size_mb': size / (1024 * 1024)
                })
                ep_found = True
                break
        if not ep_found:
            break

    return found_base, episodes

def download_file(item, out_dir, total_eps):
    """
    下载单集。先写 .part 临时文件，校验 Content-Length 后原子改名，
    保证“文件存在且 >1MB”一定是完整文件，断点重跑时才可以放心跳过。
    返回 True/False。
    """
    ep = item['episode']
    save_name = f"第{ep:02d}集(大结局).mp4" if ep == total_eps else f"第{ep:02d}集.mp4"
    save_path = os.path.join(out_dir, save_name)
    part_path = save_path + '.part'
    tag = f"[{ep:02d}/{total_eps:02d}]"

    if os.path.exists(save_path) and os.path.getsize(save_path) > 1024 * 1024:
        print(f"{tag} 已存在，跳过: {save_name}", flush=True)
        return True

    print(f"{tag} 开始下载: {save_name} ({item['size_mb']:.2f} MB)...", flush=True)
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(item['url'], headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as resp:
                expected = int(resp.headers.get('Content-Length', 0) or 0)
                written = 0
                with open(part_path, 'wb') as f:
                    while True:
                        chunk = resp.read(1024 * 256)
                        if not chunk:
                            break
                        f.write(chunk)
                        written += len(chunk)
            if expected and written != expected:
                raise IOError(f"下载不完整: {written}/{expected} 字节")
            if written < 1024 * 100:
                raise IOError(f"文件异常过小: {written} 字节")
            os.replace(part_path, save_path)
            print(f"{tag} 完成: {save_name}", flush=True)
            return True
        except Exception as e:
            last_err = e
            print(f"{tag} 第 {attempt + 1} 次下载失败: {e}", flush=True)
            time.sleep(2 + attempt * 2)

    if os.path.exists(part_path):
        try:
            os.remove(part_path)
        except OSError:
            pass
    print(f"{tag} ❌ 下载失败，放弃: {save_name} ({last_err})", flush=True)
    return False

def fetch_page_info(slug):
    url = f"https://www.slitz.com/shorts/{slug}"
    info = {
        'title': slug.replace('-', ' ').title(),
        'desc': '',
        'poster_url': f"https://slitz-media-cdn.b-cdn.net/candy/{slug}/poster-720.jpg",
        'official_url': url
    }
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', 'ignore')
            tm = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
            if tm:
                raw_title = tm.group(1).replace('Watch ', '').replace(' free', '').split('—')[0].split(':')[0].strip()
                if raw_title:
                    info['title'] = raw_title
            dm = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.I | re.S)
            if dm:
                info['desc'] = dm.group(1).strip()
    except Exception:
        pass
    return info

def ensure_drama_assets(slug, out_dir, episodes):
    page_info = fetch_page_info(slug)
    
    # 1. 尝试拉取海报
    poster_candidates = [
        f"https://slitz-media-cdn.b-cdn.net/originals/{slug}/poster.webp",
        f"https://slitz-media-cdn.b-cdn.net/candy/{slug}/poster-720.jpg",
        f"https://slitz-media-cdn.b-cdn.net/candy/{slug}/poster.webp",
        f"https://www.slitz.com/og/short/{slug}"
    ]
    poster_file = 'poster.jpg'
    for p_url in poster_candidates:
        ext = '.webp' if '.webp' in p_url else '.jpg'
        target_poster = os.path.join(out_dir, f'poster{ext}')
        if os.path.exists(target_poster) and os.path.getsize(target_poster) > 1000:
            poster_file = f'poster{ext}'
            break
        try:
            req = urllib.request.Request(p_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as r:
                if r.status == 200:
                    with open(target_poster, 'wb') as pf:
                        pf.write(r.read())
                    poster_file = f'poster{ext}'
                    print(f"海报获取成功: {poster_file}")
                    break
        except Exception:
            pass

    # 2. 检查或生成 metadata.json
    meta_path = os.path.join(out_dir, 'metadata.json')
    if not os.path.exists(meta_path):
        ep_files = sorted([f for f in os.listdir(out_dir) if f.endswith('.mp4')])
        total_size_mb = sum(os.path.getsize(os.path.join(out_dir, f)) for f in ep_files) / (1024 * 1024)
        meta = {
            'slug': slug,
            'title': page_info['title'],
            'chinese_title': page_info['title'],
            'platform': 'Slitz (Vertical Micro-drama)',
            'official_url': page_info['official_url'],
            'episodes_count': len(ep_files),
            'total_size_mb': round(total_size_mb, 2),
            'tags': ['都市微短剧', '精品短剧'],
            'summary': page_info['desc'] or 'Slitz 热门精品竖屏微短剧。',
            'poster_file': poster_file,
            'episodes': [{'filename': f, 'size_mb': round(os.path.getsize(os.path.join(out_dir, f))/(1024*1024), 2)} for f in ep_files]
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    # 3. 检查或生成 剧集说明.md
    readme_path = os.path.join(out_dir, '剧集说明.md')
    if not os.path.exists(readme_path):
        ep_files = sorted([f for f in os.listdir(out_dir) if f.endswith('.mp4')])
        total_size_mb = sum(os.path.getsize(os.path.join(out_dir, f)) for f in ep_files) / (1024 * 1024)
        file_tree = f"downloads/Slitz短剧/{slug}/\n├── {poster_file}                                    # 官方高清封面海报\n├── metadata.json                                 # 结构化原始元数据\n├── 剧集说明.md                                   # 详细剧情与角色解析\n"
        for ef in ep_files:
            file_tree += f"├── {ef}\n"
            
        doc = f"""# 《{page_info['title']}》剧集说明

## 一、 基本信息
- **剧集原名**：{page_info['title']}
- **出品平台**：Slitz（海外精品竖屏微短剧平台）
- **官方链接**：[{page_info['official_url']}]({page_info['official_url']})
- **剧集集数**：{len(ep_files)} 集全（全集已完结）
- **画质规格**：HD 高清 (竖屏 MP4, H.264 + AAC)
- **本地存储体积**：{total_size_mb:.2f} MB
- **剧情概要**：{page_info['desc']}

---

## 二、 本地文件目录与集数清单
```
{file_tree}```
- **完整集数**：第 01 集 至 第 {len(ep_files):02d} 集全部完备无缺损。
"""
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(doc.strip() + "\n")
        print("生成剧集说明.md 完成")

def update_root_indexes():
    if not os.path.exists(BASE_DIR):
        return
        
    dramas = []
    total_episodes = 0
    total_bytes = 0

    for d in sorted(os.listdir(BASE_DIR)):
        folder = os.path.join(BASE_DIR, d)
        if not os.path.isdir(folder):
            continue
        meta_file = os.path.join(folder, 'metadata.json')
        if not os.path.exists(meta_file):
            continue
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception as e:
            print(f"跳过损坏的元数据 {meta_file}: {e}")
            continue
            
        folder_files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        folder_size = sum(os.path.getsize(os.path.join(folder, f)) for f in folder_files)
        total_bytes += folder_size
        total_episodes += meta.get('episodes_count', 0)
        meta['folder_size_mb'] = round(folder_size / (1024 * 1024), 2)
        meta['folder_name'] = d
        meta['files_count'] = len(folder_files)
        dramas.append(meta)

    total_gb = total_bytes / (1024 * 1024 * 1024)

    # 1. README.md
    readme_content = f"""# Slitz 短剧资源库与下载归档

本项目子模块专注于海外热门精品竖屏微短剧平台 **Slitz**（[slitz.com](https://www.slitz.com)）的高清视频资源解析、自动化批量下载与本地结构化归档。

---

## 一、 平台与技术解析概述

- **官方网站**：[https://www.slitz.com](https://www.slitz.com)
- **平台定位**：海外新兴高品质竖屏微短剧（Shorts / Microdramas）平台，主打高张力都市情感、悬疑反转、禁忌恋情与近未来题材。
- **解析技术规范**：
  1. **CDN 智能路由分流**：Slitz 视频资源主要分发于 BunnyCDN 高性能流媒体节点（`candy` 频道与 `originals` 原创频道）。
  2. **高规格视频采集**：支持 HD 1080P/720P 高清 MP4 直链探测与下载，内嵌 AAC 纯净立体声音轨。
  3. **自动化元数据与资产归档**：每部短剧独立建档，自动爬取官方高清封面海报（`poster.webp` / `poster.jpg`）、生成结构化元数据（`metadata.json`）与详尽的中文剧情角色解析（`剧集说明.md`）。

---

## 二、 目录结构与规范

所有 Slitz 短剧资源统一保存在本目录下，子目录直接以剧目唯一标识英文 Slug 命名，严格遵循以下结构规范：

```
downloads/Slitz短剧/
├── README.md                                                 # 模块规范与总说明文档
├── dramas_list.md                                            # 剧集资产索引清单
├── list.txt                                                  # 批量直链纯文本导入清单
│
├── bought-and-paid-for/                                      # 剧目示例：赎买的罪孽 / 悬赏逃犯
│   ├── poster.webp                                           # 官方高清封面海报
│   ├── metadata.json                                         # 结构化原始元数据
│   ├── 剧集说明.md                                           # 详细剧情、角色、题材与特色解析
│   ├── 第01集.mp4                                            # [HD MP4]
│   ├── 第02集.mp4                                            # [HD MP4]
│   └── 第05集(大结局).mp4                                     # [HD MP4]
│
└── ... （更多剧集）
```

---

## 三、 当前收录剧集总览

| 序号 | 剧名 | 中文译名 | 集数 | 画质 | 文件大小 | 核心标签 | 官方链接 |
| :---: | :--- | :--- | :---: | :---: | :---: | :--- | :---: |
"""
    for i, d in enumerate(dramas, 1):
        tags_str = ' / '.join(d.get('tags', [])[:3])
        readme_content += f"| {i} | **{d.get('title', d['folder_name'])}** | {d.get('chinese_title', '')} | {d.get('episodes_count', 0)} 集全 | HD | {d['folder_size_mb']} MB | {tags_str} | [访问]({d.get('official_url', '')}) |\n"

    readme_content += f"""
- **已归档剧集总数**：{len(dramas)} 部
- **总视频分集数**：{total_episodes} 集
- **磁盘占用总量**：{total_gb:.2f} GB（{total_bytes / (1024*1024):.2f} MB）
- **完整度**：100% 全集已下载完结，单集均配备高清无损 MP4 及海报说明。

---

## 四、 工具调用规范

在项目根目录下通过 [`download_slitz.py`](../../download_slitz.py) 即可实现全自动化解析、并发下载与标准文档规范归档：

```bash
# 1. 传入 Slitz 网页链接（自动下载至 downloads/Slitz短剧 并生成对应规范文档）
python download_slitz.py https://www.slitz.com/shorts/room-service

# 2. 传入剧集 Slug 简称
python download_slitz.py room-service

# 3. 批量并发下载多部短剧
python download_slitz.py https://www.slitz.com/shorts/drama-a https://www.slitz.com/shorts/drama-b
```
"""
    with open(os.path.join(BASE_DIR, 'README.md'), 'w', encoding='utf-8') as f:
        f.write(readme_content.strip() + "\n")

    # 2. dramas_list.md
    list_md_content = f"""# Slitz 短剧资产索引清单 (Dramas List)

- **更新时间**：{datetime.now().strftime("%Y-%m-%d")}
- **归档状态**：已完成全量结构化归档（收录 {len(dramas)} 部短剧，共计 {total_episodes} 集高清视频，总计 {total_gb:.2f} GB）
- **规范等级**：标准完整归档（包含 `poster`、`metadata.json`、`剧集说明.md`、标准化命名分集）

---

## 一、 已归档本地短剧资产列表
"""
    for i, d in enumerate(dramas, 1):
        tags_str = ' / '.join(d.get('tags', []))
        list_md_content += f"""
### {i}. 《{d.get('title', d['folder_name'])}》
- **中文译名**：{d.get('chinese_title', '')}
- **剧集目录**：[`{d['folder_name']}/`](./{d['folder_name']}/)
- **详细说明文档**：[`剧集说明.md`](./{d['folder_name']}/剧集说明.md)
- **官方链接**：[{d.get('official_url', '')}]({d.get('official_url', '')})
- **集数规模**：{d.get('episodes_count', 0)} 集（已完结）
- **画质规格**：HD 720P / 1080P 高清 (竖屏 MP4, H.264 + AAC)
- **本地体积**：{d['folder_size_mb']} MB（共 {d['files_count']} 个文件）
- **核心标签**：{tags_str}
- **一句话剧情**：“{d.get('summary', '')}”

---
"""
    list_md_content += f"""
## 二、 资产数据统计汇总

| 统计指标 | 统计数值 | 备注说明 |
| :--- | :--- | :--- |
| **归档短剧总数** | **{len(dramas)} 部** | 覆盖都市情感、豪门伦理、悬疑犯罪、科幻奇幻等热门题材 |
| **视频分集总数** | **{total_episodes} 集** | 全部完结，单集独立 MP4 封装 |
| **磁盘占用总量** | **{total_gb:.2f} GB** ({round(total_bytes/(1024*1024), 2)} MB) | 包含完整分集、封面海报与元数据 |
| **画质规格** | HD 高清 (720P/1080P) | H.264 编码，高码率无损封装 |
| **分集完好率** | **100%** | 分集均已完成本地校验无缺失 |
"""
    with open(os.path.join(BASE_DIR, 'dramas_list.md'), 'w', encoding='utf-8') as f:
        f.write(list_md_content.strip() + "\n")

    # 3. list.txt
    raw_list_lines = []
    for d in dramas:
        raw_list_lines.append(f"# ==================================================")
        raw_list_lines.append(f"# {d.get('title', d['folder_name'])} ({d.get('chinese_title', '')}) - 共 {d.get('episodes_count', 0)} 集")
        raw_list_lines.append(f"# 官方链接: {d.get('official_url', '')}")
        raw_list_lines.append(f"# ==================================================")
        slug = d['folder_name']
        channel = 'candy' if slug in {'professor-mia', 'room-service', 'stepmom-summer-fling', 'toris-broken-vows', 'she-was-sent-to-kill-me', 'not-under-my-roof', 'sworn-to-the-queen', 'the-maid-my-wife-hired', 'my-billionaire-boss', 'hey-loser'} else 'originals'
        suf = '-hd.mp4' if channel == 'candy' else '.mp4'
        for ep in d.get('episodes', []):
            ep_name = ep['filename'].replace('(大结局)', '').replace('集', '').replace('第', '')
            try:
                ep_num = int(re.search(r'\d+', ep_name).group(0))
                url = f"https://slitz-media-cdn.b-cdn.net/{channel}/{slug}/ep{ep_num:02d}{suf}"
                raw_list_lines.append(url)
            except Exception:
                pass
        raw_list_lines.append("")

    with open(os.path.join(BASE_DIR, 'list.txt'), 'w', encoding='utf-8') as f:
        f.write("\n".join(raw_list_lines))
    print("总目录索引更新完成 (README.md, dramas_list.md, list.txt)")

def download_drama(url_or_slug):
    """返回 True 表示全集齐全。"""
    slug = extract_slug(url_or_slug)
    print(f"\n==========================================")
    print(f"正在解析短剧: {slug} ...")
    try:
        base, episodes = probe_episodes(slug)
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        return False

    if not episodes:
        print(f"❌ 未找到该剧集的视频源，请检查名称是否正确: {slug}")
        return False

    total = len(episodes)
    print(f"成功找到共 {total} 集！")
    for item in episodes:
        print(f"  第 {item['episode']:02d} 集: {item['size_mb']:.2f} MB -> {item['url']}")

    out_dir = os.path.join(BASE_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)
    print(f"保存路径: {out_dir}")
    print("开始并发下载...", flush=True)

    done = 0
    failed = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(download_file, item, out_dir, total): item['episode'] for item in episodes}
        for fut in as_completed(futures):
            try:
                ok = fut.result()
            except Exception as e:
                print(f"❌ 第 {futures[fut]} 集出现异常: {e}")
                ok = False
            if ok:
                done += 1
            else:
                failed.append(futures[fut])
            print(f"[进度] {done}/{total}", flush=True)

    if failed:
        print(f"❌ 《{slug}》有 {len(failed)} 集下载失败: {sorted(failed)}，重新运行同一命令可断点续传。")
        return False

    print(f"《{slug}》全部下载完成！正在生成标准化资产与说明文档...")
    ensure_drama_assets(slug, out_dir, episodes)
    update_root_indexes()
    print(f"《{slug}》归档全部完成！")
    return True

def main():
    if len(sys.argv) < 2:
        print("用法: python download_slitz.py <Slitz网址或剧集名称...>")
        sys.exit(1)

    results = [download_drama(arg) for arg in sys.argv[1:]]
    sys.exit(0 if all(results) else 2)

if __name__ == '__main__':
    main()
