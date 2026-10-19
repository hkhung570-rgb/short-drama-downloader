#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄果短剧 (https://xn--gtvs14j.online/en/) 批量 URL 提取工具
支持：
  1. 提取当前页面 (/en/) 的全部短剧链接、海报封面图片直链、导航分类与官方关联站点链接
  2. 提取整站 (Sitemap) 全部 248 部短剧及全部封面图 URL
  3. 导出为 IDM/aria2/wget 可用的文本文件 (.txt) 及结构化 JSON 文件
"""

import sys
import os
import re
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()

def extract_from_en_page(page_url="https://xn--gtvs14j.online/en/"):
    html = fetch(page_url).decode("utf-8", "ignore")

    # 1. 提取所有短剧链接和标题
    # <a class="hg-card" href="/drama/..." data-title="标题" ...>
    dramas = []
    seen_dramas = set()
    
    # 从 card 中提取
    cards = re.findall(r'<a\s+[^>]*href=["\'](/drama/[^"\']+)["\'][^>]*data-title=["\']([^"\']+)["\'][^>]*>', html)
    for path, title in cards:
        full_url = urllib.parse.urljoin(page_url, path)
        if full_url not in seen_dramas:
            seen_dramas.add(full_url)
            dramas.append({"title": title, "url": full_url})

    # 从其他 a 标签中查漏补缺
    all_a = re.findall(r'<a\s+[^>]*href=["\'](/drama/[^"\']+)["\'][^>]*>(.*?)</a>', html, re.S)
    for path, text in all_a:
        full_url = urllib.parse.urljoin(page_url, path)
        if full_url not in seen_dramas:
            seen_dramas.add(full_url)
            clean_title = re.sub(r'<[^>]+>', ' ', text).strip()
            clean_title = ' '.join(clean_title.split())
            dramas.append({"title": clean_title or urllib.parse.unquote(path.strip('/').split('/')[-1]), "url": full_url})

    # 2. 提取封面图片 URL (img src="/covers/...")
    covers = []
    seen_covers = set()
    imgs = re.findall(r'<img\s+[^>]*src=["\']([^"\']+)["\']', html)
    for src in imgs:
        full_src = urllib.parse.urljoin(page_url, src)
        if "/covers/" in full_src and full_src not in seen_covers:
            seen_covers.add(full_src)
            covers.append(full_src)

    # 3. 提取外部官方产品链接
    official_products = []
    seen_ext = set()
    for ext in ["https://huangguodrama.ai/", "https://huangguo.chat/", "https://huangguo.design/"]:
        if ext in html and ext not in seen_ext:
            seen_ext.add(ext)
            official_products.append(ext)

    # 4. 栏目分类链接
    genres = []
    for g_path in re.findall(r'href=["\'](/genre/[^"\']+)["\']', html):
        full_g = urllib.parse.urljoin(page_url, g_path)
        if full_g not in genres:
            genres.append(full_g)

    return {
        "page": page_url,
        "dramas_count": len(dramas),
        "dramas": dramas,
        "covers_count": len(covers),
        "covers": covers,
        "official_products": official_products,
        "genres": genres,
    }

def extract_all_from_sitemap(base_url="https://xn--gtvs14j.online"):
    sitemap_url = f"{base_url}/sitemap.xml"
    content = fetch(sitemap_url)
    root = ET.fromstring(content)
    ns = {
        "s": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "image": "http://www.google.com/schemas/sitemap-image/1.1"
    }

    all_dramas = []
    all_covers = []
    all_pages = []

    for url_tag in root.findall("s:url", ns):
        loc = url_tag.find("s:loc", ns)
        if loc is None or not loc.text:
            continue
        page_loc = loc.text.strip()
        all_pages.append(page_loc)

        if "/drama/" in page_loc:
            # 提取剧名
            slug_part = page_loc.rstrip("/").split("/")[-1]
            title = urllib.parse.unquote(slug_part)
            all_dramas.append({"title": title, "url": page_loc})

        # 检查图片
        for img_tag in url_tag.findall("image:image", ns):
            img_loc = img_tag.find("image:loc", ns)
            if img_loc is not None and img_loc.text:
                c_url = img_loc.text.strip()
                if c_url not in all_covers:
                    all_covers.append(c_url)

    return {
        "sitemap_url": sitemap_url,
        "total_urls": len(all_pages),
        "total_dramas": len(all_dramas),
        "total_covers": len(all_covers),
        "dramas": all_dramas,
        "covers": all_covers,
        "all_pages": all_pages
    }

def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    print("[1/2] 正在解析目标页面: https://xn--gtvs14j.online/en/ ...")
    en_data = extract_from_en_page()
    print(f"      - 发现短剧: {en_data['dramas_count']} 部")
    print(f"      - 发现封面图片: {en_data['covers_count']} 张")
    print(f"      - 官方平台: {en_data['official_products']}")

    print("[2/2] 正在通过 Sitemap 解析全站完整清单 ...")
    site_data = extract_all_from_sitemap()
    print(f"      - 全站短剧总数: {site_data['total_dramas']} 部")
    print(f"      - 全站封面图片总数: {site_data['total_covers']} 张")
    print(f"      - 全站收录页面总数: {site_data['total_urls']} 个")

    # 导出文件
    # 1. en 页面短剧列表
    en_drama_txt = os.path.join(out_dir, "en_page_dramas.txt")
    with open(en_drama_txt, "w", encoding="utf-8") as f:
        for d in en_data["dramas"]:
            f.write(f"{d['title']}\t{d['url']}\n")

    # 2. en 页面封面图片下载列表 (用于 IDM/wget/aria2)
    en_covers_txt = os.path.join(out_dir, "en_page_covers.txt")
    with open(en_covers_txt, "w", encoding="utf-8") as f:
        for c in en_data["covers"]:
            f.write(f"{c}\n")

    # 3. 全站 248 部短剧完整 URL 列表
    all_dramas_txt = os.path.join(out_dir, "all_dramas_full.txt")
    with open(all_dramas_txt, "w", encoding="utf-8") as f:
        for d in site_data["dramas"]:
            f.write(f"{d['title']}\t{d['url']}\n")

    # 4. 全站封面图片列表
    all_covers_txt = os.path.join(out_dir, "all_covers_full.txt")
    with open(all_covers_txt, "w", encoding="utf-8") as f:
        for c in site_data["covers"]:
            f.write(f"{c}\n")

    # 5. 完整 JSON 数据
    summary_json = os.path.join(out_dir, "extracted_urls.json")
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump({
            "en_page": en_data,
            "full_sitemap": site_data
        }, f, ensure_ascii=False, indent=2)

    print("\n[完成] 批量提取完成，文件已生成：")
    print(f"  1. 当前英文页短剧清单 ({en_data['dramas_count']}部): {en_drama_txt}")
    print(f"  2. 当前英文页封面图清单 ({en_data['covers_count']}张): {en_covers_txt}")
    print(f"  3. 全站完整短剧清单 ({site_data['total_dramas']}部): {all_dramas_txt}")
    print(f"  4. 全站封面图清单 ({site_data['total_covers']}张): {all_covers_txt}")
    print(f"  5. 结构化汇总文件 (JSON): {summary_json}")

if __name__ == "__main__":
    main()
