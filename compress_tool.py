#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
短剧视频批量压缩与归档打包工具
功能特性:
  1. 智能检测硬件加速编码器 (Intel QSV hevc_qsv / h264_qsv, NVIDIA NVENC, CPU libx265 / libx264)
  2. 支持单文件压缩、整部短剧文件夹批量压缩、全平台下载目录递归压缩
  3. 支持安全替换模式 (--replace)：仅当新文件宽高比/时长一致且体积更小时才替换，否则保留原片
  4. 已经是目标编码的视频自动跳过 (避免重复转码损失画质)，可用 --force 强制重压
  5. 硬件编码失败/画面比例异常时自动回退到 CPU 编码重试
  6. 支持目录归档打包为标准 ZIP 压缩包 (--zip)，先写临时文件再原子改名
  7. 自动统计压缩前后体积对比、压缩比与耗时

退出码: 0 = 全部成功 (含跳过), 1 = 参数/路径错误, 2 = 有视频压缩失败

使用示例:
  python compress_tool.py "downloads/Slitz短剧/room-service"
  python compress_tool.py "downloads/Slitz短剧/room-service" --replace
  python compress_tool.py "downloads/Reelshort/Number One, Nobody" --codec h264
  python compress_tool.py "downloads/Reelshort/Number One, Nobody" --crf 28 --replace
  python compress_tool.py --zip "downloads/Slitz短剧/room-service"
"""

import sys
import os
import re
import argparse
import subprocess
import time
import zipfile
import imageio_ffmpeg

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

# 单个视频压缩超时 (秒)。短剧单集通常 1~3 分钟，30 分钟足够覆盖最慢的 CPU 编码。
COMPRESS_TIMEOUT = 30 * 60
# 压缩后时长与原片允许的最大偏差 (秒)
DURATION_TOLERANCE = 1.5

_SKIP_SUFFIXES = (".compressed.mp4", ".temp.mp4")


def _is_hevc(codec):
    return codec.lower() in ("hevc", "h265", "x265")


def detect_best_encoder(codec="hevc"):
    """
    智能探测系统支持的最佳视频编码器
    codec: 'hevc' (H.265) 或 'h264' (H.264)
    返回 (encoder, 描述)
    """
    if _is_hevc(codec):
        candidates = [
            ("hevc_qsv", "Intel QuickSync 硬件加速 (HEVC)"),
            ("hevc_nvenc", "NVIDIA NVENC 硬件加速 (HEVC)"),
            ("libx265", "CPU 软件编码 (libx265)"),
        ]
    else:
        candidates = [
            ("h264_qsv", "Intel QuickSync 硬件加速 (H.264)"),
            ("h264_nvenc", "NVIDIA NVENC 硬件加速 (H.264)"),
            ("libx264", "CPU 软件编码 (libx264)"),
        ]

    for enc, desc in candidates:
        cmd = [
            FFMPEG_EXE, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "nullsrc=s=256x256:d=1",
            "-c:v", enc,
            "-f", "null", "-",
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            if res.returncode == 0:
                return enc, desc
        except Exception:
            continue

    fallback = cpu_encoder_for(codec)
    return fallback, f"默认 CPU 编码 ({fallback})"


def cpu_encoder_for(codec):
    return "libx265" if _is_hevc(codec) else "libx264"


def _ffmpeg_info(path):
    """ffmpeg -i 的 stderr 输出 (imageio-ffmpeg 不带 ffprobe)。失败返回空串。"""
    try:
        res = subprocess.run([FFMPEG_EXE, "-hide_banner", "-nostdin", "-i", path],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    except Exception:
        return ""
    return res.stderr.decode("utf-8", "ignore")


def parse_probe_output(text):
    """从 ffmpeg -i 输出解析 codec 与时长，解析失败返回 None。"""
    m_dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    m_vid = re.search(r"Stream #\S+.*?Video:\s*([A-Za-z0-9_]+)", text)
    if not m_dur or not m_vid:
        return None
    h, m, s = int(m_dur.group(1)), int(m_dur.group(2)), float(m_dur.group(3))
    return {"codec": m_vid.group(1).lower(), "duration": h * 3600 + m * 60 + s}


def probe_video(path):
    return parse_probe_output(_ffmpeg_info(path))


def display_size(path):
    """读取视频的显示宽高（按 SAR 和旋转标记换算），读取失败返回 None。"""
    out = _ffmpeg_info(path)
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


def _build_cmd(src_path, out_path, encoder, quality, codec):
    # ⚠️ 宽高比保护滤镜（对所有编码器均生效）：
    #   - trunc(iw/2)*2 / trunc(ih/2)*2 : 宽高圆整为偶数，仅确保编码兼容性
    #   - setsar=1 : 明确 SAR 为 1:1，防止播放器因 SAR 元数据异常而拉伸显示
    vf_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1"
    cmd = [
        FFMPEG_EXE, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-i", src_path,
        "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", vf_filter,
        "-c:v", encoder,
    ]
    if "qsv" in encoder:
        cmd.extend(["-global_quality", str(quality), "-look_ahead", "0"])
    elif "nvenc" in encoder:
        cmd.extend(["-cq", str(quality), "-preset", "p4"])
    else:
        cmd.extend(["-crf", str(quality), "-preset", "medium"])

    # HEVC 写入 MP4 时打上 hvc1 标签，Apple 设备/QuickTime 才能直接播放
    if _is_hevc(codec):
        cmd.extend(["-tag:v", "hvc1"])

    cmd.extend(["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-f", "mp4", out_path])
    return cmd


def compress_single_video(src_path, out_path, encoder, quality=26, codec="hevc"):
    """
    压缩单个 MP4。返回 (ok, out_size, duration, err_msg)。
    严格保持原片宽高比 (见 aspect_preserved)，不一致则丢弃结果并视为失败。
    """
    cmd = _build_cmd(src_path, out_path, encoder, quality, codec)
    start_t = time.time()
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=COMPRESS_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, 0, time.time() - start_t, f"压缩超时 (>{COMPRESS_TIMEOUT // 60} 分钟)"
    duration = time.time() - start_t

    if res.returncode != 0 or not os.path.exists(out_path):
        return False, 0, duration, res.stderr.decode("utf-8", "ignore").strip()

    ok, detail = aspect_preserved(src_path, out_path)
    if not ok:
        os.remove(out_path)
        return False, 0, duration, "宽高比校验失败，已丢弃压缩结果：" + detail

    return True, os.path.getsize(out_path), duration, ""


def collect_videos(target_path):
    """收集待压缩视频，跳过备份目录(_ 或 . 开头)、临时文件、已压缩副本。"""
    videos = []
    if os.path.isfile(target_path):
        low = target_path.lower()
        if low.endswith(".mp4") and not low.endswith(_SKIP_SUFFIXES):
            videos.append(target_path)
        return videos

    for root, dirs, files in os.walk(target_path):
        dirs[:] = sorted(d for d in dirs if not d.startswith(("_", ".")))
        for f in sorted(files):
            low = f.lower()
            if low.endswith(".mp4") and not low.endswith(_SKIP_SUFFIXES):
                videos.append(os.path.join(root, f))
    return videos


def recover_leftovers(video_files):
    """上次异常中断遗留的 .bak / .temp.mp4 处理：原片丢失则从 .bak 还原，临时文件一律清掉。"""
    for v in video_files:
        bak = v + ".bak"
        if os.path.exists(bak) and not os.path.exists(v):
            os.replace(bak, v)
            print(f"  ↩ 已从上次中断的备份还原: {os.path.basename(v)}")
        tmp = v + ".temp.mp4"
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _replace_original(v_path, temp_out):
    """原子替换：原片→.bak，新片→原名，成功后删 .bak；任一步失败都还原原片。"""
    bak = v_path + ".bak"
    os.replace(v_path, bak)
    try:
        os.replace(temp_out, v_path)
    except Exception:
        os.replace(bak, v_path)
        raise
    try:
        os.remove(bak)
    except OSError:
        pass


def _remove_quiet(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def process_path(target_path, codec="hevc", quality=26, replace=False, dry_run=False, force=False):
    """
    批量或单文件处理压缩。返回 (成功数, 跳过数, 失败数)；路径错误返回 None。
    """
    target_path = os.path.abspath(target_path)
    if not os.path.exists(target_path):
        print(f"❌ 路径不存在: {target_path}")
        return None

    video_files = collect_videos(target_path)
    if not video_files:
        print("⚠️ 未找到待压缩的 MP4 视频文件。")
        return 0, 0, 0

    if dry_run:
        total_orig = sum(os.path.getsize(f) for f in video_files)
        print(f"[预检模式] 找到 {len(video_files)} 个文件，当前总体积: {total_orig / (1024*1024):.2f} MB")
        for f in video_files:
            print(f"  - {os.path.basename(f)} ({os.path.getsize(f) / (1024*1024):.2f} MB)")
        return 0, 0, 0

    recover_leftovers(video_files)

    encoder, enc_desc = detect_best_encoder(codec)
    print("=" * 65)
    print("🚀 短剧视频智能压缩引擎启动")
    print(f"待处理视频: {len(video_files)} 个")
    print(f"选择编码体系: {codec.upper()}")
    print(f"采用编码器: {encoder} ({enc_desc})")
    print(f"画质等级 (CRF/Global Quality): {quality}")
    print(f"处理模式: {'安全替换原文件' if replace else '另存为 .compressed.mp4'}")
    print("=" * 65, flush=True)

    target_codec = "hevc" if _is_hevc(codec) else "h264"
    total_orig_bytes = 0
    total_new_bytes = 0
    success_count = skip_count = fail_count = 0
    start_all = time.time()
    cpu_enc = cpu_encoder_for(codec)

    for idx, v_path in enumerate(video_files, 1):
        orig_size = os.path.getsize(v_path)
        total_orig_bytes += orig_size
        total_new_bytes += orig_size  # 先按“未变化”计，成功压缩后再修正
        filename = os.path.basename(v_path)
        dir_name = os.path.dirname(v_path)
        tag = f"[{idx}/{len(video_files)}]"

        src_info = probe_video(v_path)
        if src_info is None:
            print(f"{tag} ❌ 无法读取视频信息，文件可能已损坏，跳过: {filename}", flush=True)
            fail_count += 1
            continue

        if not force and src_info["codec"] == target_codec:
            print(f"{tag} ⏭ 已是 {src_info['codec'].upper()} 编码，跳过: {filename}", flush=True)
            skip_count += 1
            continue

        temp_out = v_path + ".temp.mp4"
        final_out = v_path if replace else os.path.join(dir_name, f"{os.path.splitext(filename)[0]}.compressed.mp4")

        print(f"{tag} 正在压缩: {filename} ({orig_size / (1024*1024):.2f} MB)...", flush=True)

        used_encoder = encoder
        ok, new_size, dur, err_msg = compress_single_video(v_path, temp_out, used_encoder, quality, codec)
        if not ok and used_encoder != cpu_enc:
            print(f"{tag} ⚠️ {used_encoder} 压缩失败 ({err_msg[:80]})，回退 CPU 编码重试...", flush=True)
            _remove_quiet(temp_out)
            used_encoder = cpu_enc
            ok, new_size, dur, err_msg = compress_single_video(v_path, temp_out, used_encoder, quality, codec)

        if ok and new_size > 10 * 1024:
            out_info = probe_video(temp_out)
            if out_info is None or abs(out_info["duration"] - src_info["duration"]) > DURATION_TOLERANCE:
                got = "无法读取" if out_info is None else f"{out_info['duration']:.1f}s"
                ok = False
                err_msg = f"时长校验失败 (原片 {src_info['duration']:.1f}s / 新片 {got})"
            elif replace and new_size >= orig_size:
                print(f"{tag} ⏭ 压缩后 {new_size / (1024*1024):.2f} MB 不小于原片，保留原片: {filename}", flush=True)
                _remove_quiet(temp_out)
                skip_count += 1
                continue
        else:
            ok = False
            err_msg = err_msg or "输出文件异常过小"

        if ok:
            saved_ratio = (1.0 - (new_size / orig_size)) * 100
            print(f"{tag} 完成! 体积: {new_size / (1024*1024):.2f} MB (节省 {saved_ratio:.1f}%), 耗时 {dur:.1f}s [{used_encoder}]", flush=True)
            try:
                if replace:
                    _replace_original(v_path, temp_out)
                else:
                    os.replace(temp_out, final_out)
            except Exception as e:
                print(f"{tag} ⚠️ 写入结果失败，已保留原片: {e}", flush=True)
                _remove_quiet(temp_out)
                fail_count += 1
                continue
            total_new_bytes += new_size - orig_size
            success_count += 1
        else:
            print(f"{tag} ❌ 失败，保留原片: {err_msg[:160]}", flush=True)
            _remove_quiet(temp_out)
            fail_count += 1

    total_time = time.time() - start_all
    total_saved_mb = (total_orig_bytes - total_new_bytes) / (1024 * 1024)
    overall_ratio = (1.0 - (total_new_bytes / total_orig_bytes)) * 100 if total_orig_bytes > 0 else 0

    print("\n" + "=" * 65)
    print("🎉 压缩处理任务全部完成!" if fail_count == 0 else "⚠️ 压缩处理结束，但有失败项")
    print(f"成功压缩: {success_count} 个, 跳过: {skip_count} 个, 失败: {fail_count} 个 (共 {len(video_files)} 个)")
    print(f"压缩前总体积: {total_orig_bytes / (1024*1024):.2f} MB")
    print(f"压缩后总体积: {total_new_bytes / (1024*1024):.2f} MB")
    print(f"共节省磁盘空间: {total_saved_mb:.2f} MB ({overall_ratio:.1f}%)")
    print(f"总计耗时: {total_time:.1f} 秒")
    print("=" * 65)
    return success_count, skip_count, fail_count


# 已是压缩格式的文件不再 deflate，否则只会白白消耗 CPU
_STORED_EXTS = {".mp4", ".mkv", ".jpg", ".jpeg", ".png", ".webp", ".zip", ".gz", ".m4a", ".mp3"}
_ZIP_SKIP_SUFFIXES = (".temp.mp4", ".bak", ".part", ".temp.ts")


def zip_archive(folder_path, out_zip=None):
    """
    将指定目录打包为标准 ZIP 文件。先写 .tmp 再原子改名，失败不会留下半个压缩包。
    返回 True/False。
    """
    folder_path = os.path.abspath(folder_path)
    if not os.path.isdir(folder_path):
        print(f"❌ 目标不是有效目录: {folder_path}")
        return False

    folder_name = os.path.basename(folder_path.rstrip("\\/"))
    parent_dir = os.path.dirname(folder_path)
    if not out_zip:
        out_zip = os.path.join(parent_dir, f"{folder_name}.zip")
    tmp_zip = out_zip + ".tmp"

    print(f"📦 正在打包归档目录: {folder_name} -> {os.path.basename(out_zip)} ...", flush=True)
    start_t = time.time()
    total_files = 0

    try:
        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zf:
            for root, dirs, files in os.walk(folder_path):
                dirs[:] = sorted(d for d in dirs if not d.startswith("_"))
                for file in sorted(files):
                    if file.lower().endswith(_ZIP_SKIP_SUFFIXES):
                        continue
                    file_full = os.path.join(root, file)
                    arcname = os.path.join(folder_name, os.path.relpath(file_full, folder_path))
                    stored = os.path.splitext(file)[1].lower() in _STORED_EXTS
                    zf.write(file_full, arcname,
                             compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED)
                    total_files += 1
        os.replace(tmp_zip, out_zip)
    except Exception as e:
        print(f"❌ 打包失败: {e}")
        _remove_quiet(tmp_zip)
        return False

    dur = time.time() - start_t
    zip_size_mb = os.path.getsize(out_zip) / (1024 * 1024)
    print(f"✅ 打包成功! 共包含 {total_files} 个文件, 归档包大小: {zip_size_mb:.2f} MB, 耗时 {dur:.1f} 秒")
    print(f"归档包路径: {out_zip}")
    return True


def main():
    parser = argparse.ArgumentParser(description="短剧视频智能批量压缩与归档工具")
    parser.add_argument("target", nargs="?", default=None, help="目标文件路径或短剧文件夹路径")
    parser.add_argument("--codec", choices=["hevc", "h264"], default="hevc", help="压缩编码格式 (默认: hevc / H.265)")
    parser.add_argument("--crf", type=int, default=26, help="压缩画质质量等级 (默认: 26, 建议 23-30)")
    parser.add_argument("--replace", action="store_true", help="压缩完成后安全替换原视频文件 (体积更小才替换)")
    parser.add_argument("--force", action="store_true", help="即使已是目标编码也重新压缩")
    parser.add_argument("--dry-run", action="store_true", help="预检模式，仅扫描统计待压缩文件")
    parser.add_argument("--zip", help="将指定文件夹快速打包为 .zip 归档文件")
    args = parser.parse_args()

    if args.zip:
        sys.exit(0 if zip_archive(args.zip) else 1)

    if not args.target:
        parser.print_help()
        print("\n💡 提示: 请传入待压缩的短剧文件夹路径，例如:")
        print('  python compress_tool.py "downloads/Slitz短剧/room-service"')
        sys.exit(1)

    result = process_path(args.target, codec=args.codec, quality=args.crf,
                          replace=args.replace, dry_run=args.dry_run, force=args.force)
    if result is None:
        sys.exit(1)
    sys.exit(2 if result[2] > 0 else 0)


if __name__ == "__main__":
    main()
