#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄果短剧 - 互动短剧《我在合欢宗多子多福》(hehuan-sect) 完整资源与剧情树下载器
功能：
  1. 解析全分支节点、选项与结局走向
  2. 批量下载全部 19 个剧情分支的高清 MP4 视频 (总计 ~91 MB)
  3. 生成分支剧情树指南 (story_guide.md) 与结构化元数据 (story_tree.json)
"""

import os
import re
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0"
TARGET_URL = "https://huangguodrama.ai/en/interactive/hehuan-sect/"

NODE_NAME_MAP = {
    "open": "00_开局_三位仙子各怀心思",
    "a1": "A1_蓝衣仙子_撞见传信",
    "a2": "A2_蓝衣仙子_星辰宫召还",
    "a_he": "A_HE结局_星河为聘",
    "a_ne": "A_NE结局_星河两岸",
    "a_bad": "A_BAD结局_星陨崖前",
    "b1": "B1_合欢圣女_入阁试功",
    "b2": "B2_合欢圣女_解咒祭品",
    "b_he": "B_HE结局_合欢为契",
    "b_ne": "B_NE结局_桃花误期",
    "b_bad": "B_BAD结局_红绡送客",
    "c1": "C1_医仙师妹_施针手抖",
    "c2": "C2_医仙师妹_雨夜寒毒",
    "c_he": "C_HE结局_春回莲心",
    "c_ne": "C_NE结局_莲心未语",
    "c_bad": "C_BAD结局_药庐闭门",
    "harem1": "H1_齐聚一堂_仙子同门",
    "harem_true": "H_TRUE完美结局_多子多福",
    "harem_bad": "H_BAD悲惨结局_满庭花落"
}

def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", "ignore")

def extract_interactive_data(html):
    # unescape Next.js stream
    pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html)
    full_f = ""
    for p in pushes:
        try:
            s = bytes(p, "utf-8").decode("unicode_escape")
            full_f += s
        except Exception:
            full_f += p

    nodes_idx = full_f.find('"nodes":{')
    nodes = {}
    if nodes_idx != -1:
        chunk = full_f[nodes_idx+8:]
        depth = 0
        end_idx = 0
        for i, c in enumerate(chunk):
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        nodes_json = chunk[:end_idx]
        try:
            nodes = json.loads(nodes_json)
        except Exception:
            pass

    # Fallback to direct video search if nodes extraction had issues
    raw_videos = set(re.findall(r'https?://media\.huangguodrama\.ai/motion/interactive/hehuan-sect/[^\s"\'\\<>]+\.mp4', html))
    return nodes, raw_videos

def download_file(url, out_path, desc=""):
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        print(f"  [跳过已存在] {desc}")
        return True
    
    tmp_path = out_path + ".tmp"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r, open(tmp_path, "wb") as f:
                block_size = 64 * 1024
                while True:
                    chunk = r.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
            os.replace(tmp_path, out_path)
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            print(f"  [下载完成] {desc} ({size_mb:.2f} MB)")
            return True
        except Exception as e:
            time.sleep(2)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    print(f"  [下载失败] {desc}")
    return False

def main():
    print(f"=== 正在解析互动短剧: {TARGET_URL} ===")
    html = fetch_html(TARGET_URL)
    nodes, raw_videos = extract_interactive_data(html)
    
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads", "interactive_hehuan_sect")
    os.makedirs(out_dir, exist_ok=True)
    
    # 构建任务列表
    tasks_info = []
    for node_id, node_data in nodes.items():
        vurl = node_data.get("video")
        if not vurl:
            continue
        clean_name = NODE_NAME_MAP.get(node_id, f"Node_{node_id}")
        fn = f"{clean_name}.mp4"
        tasks_info.append({
            "id": node_id,
            "title": node_data.get("title", ""),
            "choices": node_data.get("choices", []),
            "url": vurl,
            "filename": fn,
            "filepath": os.path.join(out_dir, fn)
        })

    print(f"解析到剧情节点与视频数: {len(tasks_info)} 个分支")
    print(f"输出保存路径: {out_dir}\n")

    # 保存剧情树 JSON
    with open(os.path.join(out_dir, "story_tree.json"), "w", encoding="utf-8") as f:
        json.dump(nodes, f, ensure_ascii=False, indent=2)

    # 生成剧情路线攻略 Markdown
    guide_path = os.path.join(out_dir, "story_guide.md")
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write("# 《我在合欢宗多子多福》互动短剧完整剧情树与结局路线\n\n")
        f.write("本互动剧共有 **19 个视频分支片段**，包含 4 条主线剧情及 8 种结局。\n\n")
        f.write("## 一、主线分支导图\n\n")
        f.write("```\n")
        f.write("00 开局 (三位仙子各怀心思)\n")
        f.write(" ├── 路线 A: 蓝衣仙子 (冷傲师姐) ──> A1 ──> A2 ──┬──> A_HE (星河为聘)\n")
        f.write(" │                                            ├──> A_NE (星河两岸)\n")
        f.write(" │                                            └──> A_BAD (星陨崖前)\n")
        f.write(" ├── 路线 B: 合欢圣女 ────────────> B1 ──> B2 ──┬──> B_HE (合欢为契)\n")
        f.write(" │                                            ├──> B_NE (桃花误期)\n")
        f.write(" │                                            └──> B_BAD (红绡送客)\n")
        f.write(" ├── 路线 C: 医仙师妹 ────────────> C1 ──> C2 ──┬──> C_HE (春回莲心)\n")
        f.write(" │                                            ├──> C_NE (莲心未语)\n")
        f.write(" │                                            └──> C_BAD (药庐闭门)\n")
        f.write(" └── 路线 H: 齐聚后宫 ────────────> H1 ─────────┬──> H_TRUE (多子多福 完美结局)\n")
        f.write("                                              └──> H_BAD (满庭花落)\n")
        f.write("```\n\n")
        f.write("## 二、各分支对应本地视频列表\n\n")
        for item in tasks_info:
            f.write(f"- **[{item['id']}] {item['title']}**\n")
            f.write(f"  - 对应视频文件: `{item['filename']}`\n")
            if item["choices"]:
                f.write(f"  - 选择分支:\n")
                for c in item["choices"]:
                    f.write(f"    - *{c.get('label')}* -> 前往节点 `[{c.get('target')}]`\n")
            f.write("\n")

    # 开始多线程下载所有视频
    print("--- 开始下载全部 19 个剧情分支 MP4 视频 ---")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = []
        for t in tasks_info:
            futures.append(pool.submit(download_file, t["url"], t["filepath"], t["filename"]))
        results = [f.result() for f in futures]

    success_count = sum(1 for r in results if r)
    elapsed = time.time() - start_time
    print(f"\n=== 全部互动剧集下载完成 ===")
    print(f"成功: {success_count}/{len(tasks_info)} 个分支视频")
    print(f"耗时: {elapsed:.1f} 秒")
    print(f"保存目录: {out_dir}")

if __name__ == "__main__":
    main()
