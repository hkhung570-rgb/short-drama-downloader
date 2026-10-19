#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
短剧批量下载与管理平台 (Web UI & AI 智能协同服务)
集成了:
  1. 多平台短剧自动化解析下载 (ReelShort, Slitz, 黄果短剧)
  2. 智能硬件加速视频压缩 (Intel QSV / NVENC / CPU)
  3. 资产管理与在线试看海报墙 (metadata.json, 剧集说明, 在线播放)
  4. 受控并发的任务队列 (排队 / 取消 / 重试 / 重启后恢复) 与实时日志
  5. AI 智能对话助手与自然语言意图调度
  6. 标准 RESTful API，方便飞书/钉钉机器人、Dify 等第三方 Agent 接入

启动方式:
  python web_app.py --port 8000

环境变量:
  DL_WORKERS        同时执行的任务数 (默认 2；压缩阶段始终串行，避免抢占 GPU)
  DL_CORS_ORIGINS   允许跨域调用 API 的来源，逗号分隔 (默认不开放跨域)
  DL_DOWNLOADS_DIR  下载目录 (默认 ./downloads)
  DL_DATA_DIR       任务记录/日志目录 (默认 ./data)
"""

import os
import sys
import re
import json
import time
import uuid
import csv
import hmac
import io
import queue
import shutil
import socket
import threading
import subprocess
import urllib.parse
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

import trash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.abspath(os.environ.get("DL_DOWNLOADS_DIR") or os.path.join(BASE_DIR, "downloads"))
DATA_DIR = os.path.abspath(os.environ.get("DL_DATA_DIR") or os.path.join(BASE_DIR, "data"))
LOG_DIR = os.path.join(DATA_DIR, "logs")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
WEB_DIR = os.path.join(BASE_DIR, "web")
for _d in (DOWNLOADS_DIR, DATA_DIR, LOG_DIR):
    os.makedirs(_d, exist_ok=True)

WORKERS = max(1, int(os.environ.get("DL_WORKERS", "2") or 2))
TRASH_DAYS = max(1, int(os.environ.get("DL_TRASH_DAYS", str(trash.DEFAULT_RETENTION_DAYS)) or trash.DEFAULT_RETENTION_DAYS))
VERSION = "2.2.0"
MAX_TASKS_KEPT = 200
LOG_KEEP_LINES = 500

PLATFORMS = {
    "ReelShort": {"script": "download_reelshort.py", "dir": "Reelshort"},
    "Slitz": {"script": "download_slitz.py", "dir": "Slitz短剧"},
    "黄果短剧": {"script": "download_huangguo_video.py", "dir": "黄果短剧"},
}

TERMINAL = ("completed", "failed", "cancelled")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ==================== 输入解析与路径安全 ====================

_LATEST_RE = re.compile(r"^--latest(?:\s+(\d+))?$")
_SLUG_RE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$")
_BOOKID_RE = re.compile(r"^[A-Za-z0-9]{24}$")


def parse_target(raw: str) -> Dict[str, Any]:
    """
    把用户输入解析成 {platform, args, target}。无法识别/不安全的输入抛 ValueError。
    注意：args 会直接作为脚本参数，因此绝不允许以 '-' 开头的任意内容混入 (参数注入)。
    """
    t = (raw or "").strip()
    if not t:
        raise ValueError("URL 不能为空")
    if len(t) > 2048 or any(ord(c) < 32 for c in t):
        raise ValueError("链接过长或包含非法字符")

    m = _LATEST_RE.match(t)
    if m:
        n = int(m.group(1) or 2)
        if not 1 <= n <= 10:
            raise ValueError("--latest 的数量需在 1~10 之间")
        return {"platform": "ReelShort", "args": ["--latest", str(n)], "target": f"--latest {n}"}
    if t.startswith("-"):
        raise ValueError("不支持的参数，仅支持 '--latest N'")
    if re.search(r"\s", t):
        raise ValueError("链接中不能包含空白字符")

    if re.match(r"^https?://", t, re.I):
        u = urllib.parse.urlparse(t)
        host = (u.hostname or "").lower()
        if host == "reelshort.com" or host.endswith(".reelshort.com"):
            return {"platform": "ReelShort", "args": [t], "target": t}
        if host == "slitz.com" or host.endswith(".slitz.com"):
            return {"platform": "Slitz", "args": [t], "target": t}
        if "huangguo" in host or "nv5et" in host or "wrjmtnebd" in host or re.search(r"/video/\d+", u.path):
            return {"platform": "黄果短剧", "args": [t], "target": t}
        raise ValueError("暂不支持该站点，目前支持 ReelShort / Slitz / 黄果短剧")

    if _BOOKID_RE.match(t):
        return {"platform": "ReelShort", "args": [t], "target": t}
    if _SLUG_RE.match(t):
        return {"platform": "Slitz", "args": [t], "target": t}
    raise ValueError("无法识别的输入，请粘贴剧集详情页链接")


def resolve_drama_dir(rel_path: Any) -> str:
    """
    把前端传来的 '平台/剧名' 相对路径解析为下载目录内的绝对路径。
    拒绝：越界(../、绝对路径、盘符)、符号链接逃逸、下载根/平台根本身、'_' 开头的备份目录。
    返回绝对路径；非法抛 HTTPException(400)，不存在抛 404。
    """
    if not isinstance(rel_path, str) or not rel_path.strip() or "\x00" in rel_path:
        raise HTTPException(status_code=400, detail="缺少或非法的 path 参数")
    rel = rel_path.strip().replace("\\", "/").strip("/")
    parts = [p for p in rel.split("/") if p]
    if len(parts) != 2 or any(p in (".", "..") or p.startswith(("_", ".")) for p in parts):
        raise HTTPException(status_code=400, detail="path 必须形如 '平台/剧集目录'")

    base = os.path.normcase(os.path.realpath(DOWNLOADS_DIR))
    full = os.path.normcase(os.path.realpath(os.path.join(DOWNLOADS_DIR, *parts)))
    try:
        inside = os.path.commonpath([base, full]) == base and full != base
    except ValueError:  # 不同盘符
        inside = False
    if not inside:
        raise HTTPException(status_code=400, detail="path 超出下载目录范围")
    if not os.path.isdir(full):
        raise HTTPException(status_code=404, detail="目录不存在")
    return os.path.realpath(os.path.join(DOWNLOADS_DIR, *parts))


def is_inside_downloads(path: str) -> bool:
    base = os.path.normcase(os.path.realpath(DOWNLOADS_DIR))
    full = os.path.normcase(os.path.realpath(path))
    try:
        return os.path.commonpath([base, full]) == base and full != base
    except ValueError:
        return False


# ==================== 任务管理器 ====================

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.logs: Dict[str, deque] = {}
        self.procs: Dict[str, subprocess.Popen] = {}
        self.cancel_flags = set()
        self.lock = threading.RLock()
        self.save_lock = threading.Lock()
        self._pending_restore: List[str] = []
        self.queue: "queue.Queue[str]" = queue.Queue()
        self.dir_locks: Dict[str, threading.Lock] = {}
        self.compress_sem = threading.Semaphore(1)
        self.workers_started = False
        self.dramas_dirty = True
        self._load()

    # ---------- 持久化 ----------

    def _load(self):
        """启动时恢复任务记录：排队中的重新入队，运行中的标记为中断失败(可一键重试续传)。"""
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
        except FileNotFoundError:
            return
        except Exception as e:
            print(f"⚠️ 任务记录读取失败，已忽略: {e}")
            return
        requeue = []
        for t in saved:
            if not isinstance(t, dict) or "id" not in t:
                continue
            if t.get("status") == "running":
                t["status"] = "failed"
                t["error"] = "服务重启导致任务中断，点击【重试】可断点续传"
                t["finished_at"] = now_str()
            elif t.get("status") == "pending":
                requeue.append(t["id"])
            self.tasks[t["id"]] = t
        self._pending_restore = requeue

    def _save(self):
        with self.lock:  # 在锁内完成序列化，避免 worker 同时修改任务字典
            payload = json.dumps(list(self.tasks.values()), ensure_ascii=False)
        tmp = TASKS_FILE + ".tmp"
        with self.save_lock:  # 多个线程同时落盘会争用同一个临时文件
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(payload)
                os.replace(tmp, TASKS_FILE)
            except Exception as e:
                print(f"⚠️ 任务记录保存失败: {e}")

    def _log_path(self, task_id: str) -> str:
        return os.path.join(LOG_DIR, f"{task_id}.log")

    # ---------- 任务 CRUD ----------

    def create_task(self, task_type: str, target: str, platform: str, params: Optional[dict] = None) -> Dict[str, Any]:
        with self.lock:
            task_id = uuid.uuid4().hex[:8]
            task = {
                "id": task_id,
                "type": task_type,          # download / compress / zip
                "target": target,
                "platform": platform,
                "params": params or {},
                "status": "pending",        # pending / running / completed / failed / cancelled
                "progress": 0,
                "current_ep": 0,
                "total_eps": 0,
                "current_stage": "排队中...",
                "log_count": 0,
                "created_at": now_str(),
                "started_at": None,
                "finished_at": None,
                "result_dir": None,
                "result_dirs": [],
                "error": None,
                "warning": None,
                "trash_ids": [],            # 本任务产生的回收站条目 (压缩前原片)，用于“撤销压缩”
            }
            self.tasks[task_id] = task
            self.logs[task_id] = deque(maxlen=LOG_KEEP_LINES)
            self._trim()
        self._save()
        return dict(task)

    def _trim(self):
        """内存里最多保留 MAX_TASKS_KEPT 条，优先丢弃最老的已结束任务。"""
        overflow = len(self.tasks) - MAX_TASKS_KEPT
        if overflow <= 0:
            return
        for tid in [k for k, v in self.tasks.items() if v["status"] in TERMINAL][:overflow]:
            self._drop(tid)

    def _drop(self, task_id: str):
        self.tasks.pop(task_id, None)
        self.logs.pop(task_id, None)
        try:
            os.remove(self._log_path(task_id))
        except OSError:
            pass

    def find_active(self, task_type: str, target: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            for t in self.tasks.values():
                if t["type"] == task_type and t["target"] == target and t["status"] in ("pending", "running"):
                    return dict(t)
        return None

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            t = self.tasks.get(task_id)
            return dict(t, result_dirs=list(t["result_dirs"]), trash_ids=list(t.get("trash_ids", []))) if t else None

    def list_tasks(self) -> List[Dict[str, Any]]:
        """列表接口只返回摘要(不含日志)，前端每 2.5 秒轮询一次，不能随任务数增长变重。"""
        with self.lock:
            out = []
            for t in reversed(list(self.tasks.values())):
                item = dict(t, result_dirs=list(t["result_dirs"]), trash_ids=list(t.get("trash_ids", [])))
                lg = self.logs.get(t["id"])
                item["last_log"] = lg[-1] if lg else ""
                out.append(item)
            return out

    def update_task(self, task_id: str, **kwargs):
        persist = any(k in kwargs for k in ("status", "error", "warning", "result_dirs", "finished_at", "trash_ids"))
        with self.lock:
            t = self.tasks.get(task_id)
            if t is None:
                return
            t.update(kwargs)
            if kwargs.get("result_dirs"):
                t["result_dir"] = kwargs["result_dirs"][0]
        if persist:
            self._save()

    def add_trash_id(self, task_id: str, entry_id: str):
        with self.lock:
            t = self.tasks.get(task_id)
            if t is None:
                return
            t.setdefault("trash_ids", []).append(entry_id)
        self._save()

    def append_log(self, task_id: str, line: str):
        clean = line.rstrip("\r\n").strip()
        if not clean:
            return
        with self.lock:
            t = self.tasks.get(task_id)
            if t is None:
                return
            self.logs.setdefault(task_id, deque(maxlen=LOG_KEEP_LINES)).append(clean)
            t["log_count"] += 1
        try:
            with open(self._log_path(task_id), "a", encoding="utf-8") as f:
                f.write(clean + "\n")
        except OSError:
            pass

    def get_logs(self, task_id: str, tail: int = 300) -> List[str]:
        with self.lock:
            lg = self.logs.get(task_id)
            if lg:
                return list(lg)[-tail:]
        # 重启后内存里没有，回读磁盘日志
        try:
            with open(self._log_path(task_id), "r", encoding="utf-8", errors="replace") as f:
                return [ln.rstrip("\n") for ln in f.readlines()[-tail:]]
        except OSError:
            return []

    def delete_task(self, task_id: str) -> bool:
        with self.lock:
            t = self.tasks.get(task_id)
            if not t or t["status"] not in TERMINAL:
                return False
            self._drop(task_id)
        self._save()
        return True

    def clear_finished(self) -> int:
        with self.lock:
            ids = [k for k, v in self.tasks.items() if v["status"] in TERMINAL]
            for tid in ids:
                self._drop(tid)
        self._save()
        return len(ids)

    # ---------- 调度 ----------

    def submit(self, task_id: str):
        self.queue.put(task_id)

    def start_workers(self):
        if self.workers_started:
            return
        self.workers_started = True
        for i in range(WORKERS):
            threading.Thread(target=self._worker_loop, name=f"dl-worker-{i}", daemon=True).start()
        for tid in getattr(self, "_pending_restore", []):
            self.submit(tid)
        self._pending_restore = []

    def _worker_loop(self):
        while True:
            task_id = self.queue.get()
            try:
                execute_task(task_id)
            except Exception as e:  # 兜底，保证 worker 线程永不退出
                self.append_log(task_id, f"❌ 内部错误: {e}")
                self.finish(task_id, "failed", error=f"内部错误: {e}")
            finally:
                self.queue.task_done()

    def finish(self, task_id: str, status: str, error: Optional[str] = None, warning: Optional[str] = None):
        kw: Dict[str, Any] = {"status": status, "finished_at": now_str(), "error": error}
        if warning:
            kw["warning"] = warning
        if status == "completed":
            kw.update(progress=100, current_stage="已完成" if not warning else "已完成 (有警告)")
        elif status == "cancelled":
            kw.update(current_stage="已取消")
        else:
            kw.update(current_stage="失败")
        self.update_task(task_id, **kw)
        self.dramas_dirty = True

    def dir_lock(self, path: str) -> threading.Lock:
        key = os.path.normcase(os.path.realpath(path))
        with self.lock:
            return self.dir_locks.setdefault(key, threading.Lock())

    # ---------- 取消 ----------

    def is_cancelled(self, task_id: str) -> bool:
        return task_id in self.cancel_flags

    def cancel(self, task_id: str) -> bool:
        with self.lock:
            t = self.tasks.get(task_id)
            if not t or t["status"] not in ("pending", "running"):
                return False
            self.cancel_flags.add(task_id)
            was_pending = t["status"] == "pending"
            proc = self.procs.get(task_id)
        if was_pending:
            self.finish(task_id, "cancelled")
            self.cancel_flags.discard(task_id)
        elif proc is not None:
            kill_tree(proc)
        return True


task_manager = TaskManager()


def kill_tree(proc: subprocess.Popen):
    """终止进程及其子进程 (下载脚本会再起 ffmpeg，只杀父进程会留下孤儿 ffmpeg)。"""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ==================== 后台执行器 ====================

def run_cmd(task_id: str, args: List[str], line_cb=None, prefix: str = "") -> int:
    """
    运行子进程并实时把输出写入任务日志。返回退出码；被取消返回 -1。
    子进程强制 UTF-8 输出，避免 Windows 中文区域设置下 emoji/中文乱码或 UnicodeEncodeError。
    """
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    kwargs: Dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        args, cwd=BASE_DIR, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", env=env, **kwargs,
    )
    with task_manager.lock:
        task_manager.procs[task_id] = proc
    # 注册进程的瞬间若已被取消，直接杀掉
    if task_manager.is_cancelled(task_id):
        kill_tree(proc)
    try:
        for line in proc.stdout:
            task_manager.append_log(task_id, f"{prefix}{line}" if prefix else line)
            if line_cb:
                try:
                    line_cb(line)
                except Exception:
                    pass
        proc.wait()
    finally:
        with task_manager.lock:
            task_manager.procs.pop(task_id, None)
        try:
            proc.stdout.close()
        except Exception:
            pass
    if task_manager.is_cancelled(task_id):
        return -1
    return proc.returncode


def _guess_drama_dir(platform: str, target: str) -> Optional[str]:
    """脚本没打印 '保存路径' 时，根据 target 猜测落盘目录。"""
    plat_dir = PLATFORMS.get(platform, {}).get("dir")
    if not plat_dir:
        return None
    p_path = os.path.join(DOWNLOADS_DIR, plat_dir)
    if not os.path.isdir(p_path):
        return None
    m_slug = re.search(r"shorts/([a-zA-Z0-9\-]+)", target) or (re.match(r"^([A-Za-z0-9\-]+)$", target) if platform == "Slitz" else None)
    if m_slug:
        cand = os.path.join(p_path, m_slug.group(1))
        if os.path.isdir(cand):
            return cand
    m_vid = re.search(r"video/(\d+)", target)
    if m_vid:
        for d in os.listdir(p_path):
            if d.startswith(m_vid.group(1)) and os.path.isdir(os.path.join(p_path, d)):
                return os.path.join(p_path, d)
    return None


class ProgressTracker:
    """从下载脚本的输出里解析进度。进度只增不减(多集并发完成时顺序不定)。"""

    def __init__(self, task_id: str, span_start: int = 0, span_end: int = 80):
        self.task_id = task_id
        self.start, self.end = span_start, span_end
        self.dirs: List[str] = []
        self.best = 0
        self.last_error = ""

    def _set(self, cur: int, tot: int, stage: str):
        if tot <= 0:
            return
        pct = self.start + int(min(cur, tot) / tot * (self.end - self.start))
        self.best = max(self.best, pct)
        task_manager.update_task(self.task_id, current_ep=cur, total_eps=tot,
                                 progress=self.best, current_stage=stage)

    def feed(self, line: str):
        if "❌" in line:
            self.last_error = line.replace("❌", "").strip()[:200]
        m = re.search(r"保存路径:\s*(.+)", line)
        if m:
            d = m.group(1).strip()
            if d and d not in self.dirs:
                self.dirs.append(d)
                task_manager.update_task(self.task_id, result_dirs=list(self.dirs))
            return
        m = re.search(r"\[进度\]\s*(\d+)/(\d+)", line)
        if m:
            cur, tot = int(m.group(1)), int(m.group(2))
            self._set(cur, tot, f"已完成 {cur}/{tot} 集")
            return
        # 兼容旧脚本：形如 "[03/12] 完成: ..." / "已存在，跳过"
        m = re.search(r"\[(\d+)/(\d+)\]", line)
        if m and re.search(r"完成|已存在|跳过", line):
            cur, tot = int(m.group(1)), int(m.group(2))
            self._set(cur, tot, f"已完成 {cur}/{tot} 集")


def _run_compress_stage(task_id: str, dirs: List[str], span_start: int, span_end: int,
                        keep_original: bool = False) -> Optional[str]:
    """
    压缩 dirs。返回警告文本(无问题返回 None)；被取消返回 'CANCELLED'。
    keep_original=True 时，被替换的原片会移入回收站，可在“回收站/任务卡片”里一键撤销。
    """
    warnings = []
    n = len(dirs)
    for i, d in enumerate(dirs):
        base = span_start + (span_end - span_start) * i / n
        top = span_start + (span_end - span_start) * (i + 1) / n

        def cb(line, base=base, top=top):
            m = re.search(r"\[(\d+)/(\d+)\]", line)
            if m:
                cur, tot = int(m.group(1)), int(m.group(2))
                done = cur if re.search(r"完成|跳过|失败", line) else cur - 1
                task_manager.update_task(task_id, progress=int(base + (top - base) * max(done, 0) / max(tot, 1)),
                                         current_stage=f"硬件加速压缩 {cur}/{tot} 集")

        task_manager.update_task(task_id, current_stage="正在执行硬件加速压缩 (QSV / HEVC)...")
        task_manager.append_log(task_id, f"⚡ 开始压缩: {d}")
        cmd = [sys.executable, "-u", os.path.join(BASE_DIR, "compress_tool.py"), d, "--replace"]
        entry_id = None
        if keep_original:
            try:
                entry_id, backup_dir = trash.begin_compress_backup(
                    DOWNLOADS_DIR, os.path.basename(os.path.dirname(d)), os.path.basename(d))
                cmd += ["--backup-dir", backup_dir]
            except Exception as e:
                task_manager.append_log(task_id, f"⚠️ 无法创建回收站条目，本次压缩不可撤销: {e}")
        try:
            with task_manager.dir_lock(d), task_manager.compress_sem:
                if task_manager.is_cancelled(task_id):
                    return "CANCELLED"
                rc = run_cmd(task_id, cmd, line_cb=cb, prefix="[压缩] ")
        finally:
            # 无论成功/取消/异常：有原片被替换就登记为可撤销，否则清掉空条目
            if entry_id and trash.finalize_compress_backup(DOWNLOADS_DIR, entry_id):
                task_manager.add_trash_id(task_id, entry_id)
                task_manager.append_log(task_id, f"↩ 原片已保留在回收站 {TRASH_DAYS} 天内，可随时撤销压缩")
        if rc == -1:
            return "CANCELLED"
        if rc != 0:
            warnings.append(f"{os.path.basename(d)} 压缩有失败项 (code {rc})，失败的视频已保留原片")
    return "；".join(warnings) or None


def _run_zip_stage(task_id: str, dirs: List[str], span_start: int, span_end: int) -> Optional[str]:
    warnings = []
    n = len(dirs)
    for i, d in enumerate(dirs):
        task_manager.update_task(task_id, current_stage="正在生成归档 ZIP...",
                                 progress=int(span_start + (span_end - span_start) * i / n))
        with task_manager.dir_lock(d):
            rc = run_cmd(task_id, [sys.executable, "-u", os.path.join(BASE_DIR, "compress_tool.py"), "--zip", d],
                         prefix="[打包] ")
        if rc == -1:
            return "CANCELLED"
        if rc != 0:
            warnings.append(f"{os.path.basename(d)} 打包失败 (code {rc})")
    return "；".join(warnings) or None


def execute_download(task_id: str, task: Dict[str, Any]):
    params = task["params"]
    platform = task["platform"]
    spec = PLATFORMS.get(platform)
    if spec is None:
        task_manager.finish(task_id, "failed", error=f"未知平台: {platform}")
        return

    cmd = [sys.executable, "-u", os.path.join(BASE_DIR, spec["script"]), *params["args"]]
    max_eps = params.get("max_eps")
    if max_eps:
        if platform == "ReelShort":
            cmd.extend(["--max-eps", str(int(max_eps))])
        else:
            task_manager.append_log(task_id, f"ℹ️ {platform} 暂不支持限制集数，将下载全集")

    task_manager.update_task(task_id, current_stage="正在解析剧目...")
    task_manager.append_log(task_id, f"🚀 启动下载任务: {platform} {' '.join(params['args'])}")
    tracker = ProgressTracker(task_id, 0, 80)
    rc = run_cmd(task_id, cmd, line_cb=tracker.feed)

    if rc == -1:
        task_manager.finish(task_id, "cancelled")
        return
    if rc != 0:
        reason = tracker.last_error or (f"下载脚本异常退出 (code {rc})，请查看日志")
        task_manager.finish(task_id, "failed", error=f"{reason}。已下载的内容会保留，点击【重试】可断点续传")
        return
    task_manager.append_log(task_id, "✅ 视频解析与下载完成！")

    dirs = [d for d in tracker.dirs if os.path.isdir(d) and is_inside_downloads(d)]
    if not dirs:
        guess = _guess_drama_dir(platform, task["target"])
        if guess and is_inside_downloads(guess):
            dirs = [guess]
    task_manager.update_task(task_id, result_dirs=dirs)

    warnings = []
    if params.get("auto_compress", True):
        if not dirs:
            warnings.append("未能定位剧集目录，已跳过压缩")
        else:
            w = _run_compress_stage(task_id, dirs, 80, 95 if params.get("auto_zip") else 99,
                                    keep_original=bool(params.get("keep_original", False)))
            if w == "CANCELLED":
                task_manager.finish(task_id, "cancelled")
                return
            if w:
                warnings.append(w)

    if params.get("auto_zip"):
        if not dirs:
            warnings.append("未能定位剧集目录，已跳过打包")
        else:
            w = _run_zip_stage(task_id, dirs, 95, 99)
            if w == "CANCELLED":
                task_manager.finish(task_id, "cancelled")
                return
            if w:
                warnings.append(w)
            else:
                task_manager.append_log(task_id, "📦 归档 ZIP 打包完成！")

    task_manager.finish(task_id, "completed", warning="；".join(warnings) or None)


def execute_compress(task_id: str, task: Dict[str, Any]):
    d = task["target"]
    if not is_inside_downloads(d) or not os.path.isdir(d):
        task_manager.finish(task_id, "failed", error="目录不存在或不在下载目录内")
        return
    w = _run_compress_stage(task_id, [d], 0, 99, keep_original=bool(task["params"].get("keep_original", True)))
    if w == "CANCELLED":
        task_manager.finish(task_id, "cancelled")
    elif w:
        task_manager.finish(task_id, "failed", error=w)
    else:
        task_manager.finish(task_id, "completed")


def execute_zip(task_id: str, task: Dict[str, Any]):
    d = task["target"]
    if not is_inside_downloads(d) or not os.path.isdir(d):
        task_manager.finish(task_id, "failed", error="目录不存在或不在下载目录内")
        return
    w = _run_zip_stage(task_id, [d], 0, 99)
    if w == "CANCELLED":
        task_manager.finish(task_id, "cancelled")
    elif w:
        task_manager.finish(task_id, "failed", error=w)
    else:
        task_manager.finish(task_id, "completed")


def execute_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task or task["status"] != "pending":
        return  # 已被取消/删除
    task_manager.update_task(task_id, status="running", started_at=now_str(), current_stage="准备中...")
    try:
        {"download": execute_download, "compress": execute_compress, "zip": execute_zip}[task["type"]](task_id, task)
    except Exception as e:
        if task_manager.is_cancelled(task_id):
            task_manager.finish(task_id, "cancelled")
        else:
            task_manager.append_log(task_id, f"❌ 任务执行出错: {e}")
            task_manager.finish(task_id, "failed", error=str(e))
    finally:
        task_manager.cancel_flags.discard(task_id)


# ==================== 系统信息 ====================

SYSTEM_INFO: Dict[str, Any] = {"encoder": None, "encoder_desc": "检测中..."}


def _detect_encoder_bg():
    try:
        import compress_tool
        enc, desc = compress_tool.detect_best_encoder("hevc")
        SYSTEM_INFO.update(encoder=enc, encoder_desc=desc)
    except Exception as e:
        SYSTEM_INFO.update(encoder=None, encoder_desc=f"编码器检测失败: {e}")


# ---------- 访问口令 (可选) ----------
# 设置环境变量 DL_TOKEN 后，除 首页、/api/login、/api/health 外的接口与 /media 都需要口令：
#   Authorization: Bearer <口令> / X-Token: <口令> / 登录后的 cookie。未设置则保持开放(向后兼容)。

# 首页必须开放，否则设置口令后连登录框都打不开；页面本身不含数据
OPEN_API_PATHS = ("/", "/api/login", "/api/health")


def auth_token() -> str:
    return os.environ.get("DL_TOKEN", "").strip()


def is_authed(headers, cookies) -> bool:
    tok = auth_token()
    if not tok:
        return True
    auth = headers.get("authorization", "")
    given = auth[7:].strip() if auth.lower().startswith("bearer ") else (headers.get("x-token") or cookies.get("dl_token", ""))
    return hmac.compare_digest(given.encode("utf-8"), tok.encode("utf-8"))


def require_auth(request: Request):
    if request.url.path in OPEN_API_PATHS:
        return
    if not is_authed(request.headers, request.cookies):
        raise HTTPException(status_code=401, detail="需要访问口令")


class AuthedStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        from starlette.requests import HTTPConnection
        conn = HTTPConnection(scope)
        if not is_authed(conn.headers, conn.cookies):
            return Response("需要访问口令", status_code=401)
        return await super().get_response(path, scope)


# ---------- 操作记录 ----------
# 多人共用时“谁在什么时候做了什么”。只记录会改变数据的操作；前端可通过 X-Operator 头带上操作人姓名。

AUDIT_FILE = os.path.join(DATA_DIR, "audit.log")
_audit_lock = threading.Lock()


def _operator(request: Optional[Request]) -> str:
    if request is None:
        return ""
    return urllib.parse.unquote(request.headers.get("x-operator", ""))[:40]


def audit(request: Optional[Request], action: str, detail: str = ""):
    entry = {
        "time": now_str(),
        "ip": (request.client.host if request is not None and request.client else ""),
        "operator": _operator(request),
        "action": action,
        "detail": detail[:300],
    }
    with _audit_lock:
        try:
            if os.path.isfile(AUDIT_FILE) and os.path.getsize(AUDIT_FILE) > 1024 * 1024:
                os.replace(AUDIT_FILE, AUDIT_FILE + ".1")
            with open(AUDIT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass


def read_audit(limit: int = 50) -> List[Dict[str, Any]]:
    try:
        with open(AUDIT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[-max(1, min(limit, 500)):]
    except OSError:
        return []
    out = []
    for ln in reversed(lines):
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out


def _purge_loop():
    while True:
        try:
            n = trash.purge_expired(DOWNLOADS_DIR, TRASH_DAYS)
            if n:
                print(f"🧹 回收站自动清理了 {n} 个超过 {TRASH_DAYS} 天的条目")
        except Exception as e:
            print(f"⚠️ 回收站清理失败: {e}")
        time.sleep(6 * 3600)


@asynccontextmanager
async def lifespan(app_: FastAPI):
    task_manager.start_workers()
    threading.Thread(target=_detect_encoder_bg, daemon=True).start()
    threading.Thread(target=_purge_loop, daemon=True).start()
    yield


app = FastAPI(
    title="Short Drama Downloader & Toolkit",
    description="短剧批量下载与管理平台 Web API 与交互服务",
    version=VERSION,
    lifespan=lifespan,
    dependencies=[Depends(require_auth)],
)

# 默认不开放跨域：API 带有“修改磁盘文件”的能力，任意网页都能跨域调用是很危险的。
_cors = [o.strip() for o in os.environ.get("DL_CORS_ORIGINS", "").split(",") if o.strip()]
if _cors:
    app.add_middleware(CORSMiddleware, allow_origins=_cors, allow_methods=["*"], allow_headers=["*"])

# 挂载静态媒体文件，用于网页直接浏览海报和试看视频
app.mount("/media", AuthedStaticFiles(directory=DOWNLOADS_DIR), name="media")


# ==================== RESTful API ====================

class CreateTaskRequest(BaseModel):
    url: str = Field(..., max_length=2048)
    auto_compress: bool = True
    auto_zip: bool = False
    keep_original: bool = False       # 自动压缩时是否把原片留在回收站(可撤销，但会多占空间)
    max_eps: Optional[int] = Field(None, ge=1, le=999)


class BatchTaskRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, max_length=50)
    auto_compress: bool = True
    auto_zip: bool = False
    keep_original: bool = False
    max_eps: Optional[int] = Field(None, ge=1, le=999)


class PathRequest(BaseModel):
    path: str = Field(..., max_length=512)


class CompressRequest(PathRequest):
    keep_original: bool = True        # 手动压缩默认保留原片，可在回收站撤销


class PurgeRequest(BaseModel):
    ids: Optional[List[str]] = None
    all: bool = False
    confirm: bool = False             # 永久删除必须显式 confirm=true，防止误操作/Agent 误调用


class LoginRequest(BaseModel):
    token: str = Field("", max_length=256)


class AIChatRequest(BaseModel):
    message: str = Field(..., max_length=4000)


def create_download(url: str, auto_compress: bool, auto_zip: bool, max_eps: Optional[int],
                    keep_original: bool = False):
    """创建(或复用已存在的同目标进行中)下载任务。返回 (task, duplicate)。"""
    try:
        parsed = parse_target(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    dup = task_manager.find_active("download", parsed["target"])
    if dup:
        return dup, True
    task = task_manager.create_task("download", parsed["target"], parsed["platform"], {
        "args": parsed["args"],
        "auto_compress": auto_compress,
        "auto_zip": auto_zip,
        "keep_original": keep_original,
        "max_eps": max_eps,
    })
    task_manager.submit(task["id"])
    return task, False


def _with_undo(task: Dict[str, Any]) -> Dict[str, Any]:
    """给任务加上 undo_available：它产生的回收站条目是否还在(没被恢复/清理)。"""
    root = trash.trash_root(DOWNLOADS_DIR)
    task["undo_available"] = any(os.path.isdir(os.path.join(root, tid)) for tid in task.get("trash_ids", []))
    return task


@app.post("/api/tasks", tags=["任务"], summary="创建下载任务")
def create_download_task(req: CreateTaskRequest, request: Request):
    """创建短剧下载任务 (同一目标已有进行中的任务时直接返回该任务，duplicate=true)"""
    task, dup = create_download(req.url, req.auto_compress, req.auto_zip, req.max_eps, req.keep_original)
    if not dup:
        audit(request, "创建下载", f"{task['platform']} {task['target']}")
    return {
        "code": 0,
        "msg": "已有相同的进行中任务" if dup else "任务创建成功",
        "duplicate": dup,
        "task_id": task["id"],
        "task": task,
    }


@app.post("/api/tasks/batch", tags=["任务"], summary="批量创建下载任务")
def create_batch_tasks(req: BatchTaskRequest, request: Request):
    """一次提交多个链接 (最多 50 个)。逐个返回结果：成功/重复/无法识别(含原因)，互不影响。"""
    results = []
    for raw in req.urls:
        text = (raw or "").strip()
        if not text:
            continue
        item: Dict[str, Any] = {"input": text}
        try:
            task, dup = create_download(text, req.auto_compress, req.auto_zip, req.max_eps, req.keep_original)
            item.update(ok=True, task_id=task["id"], duplicate=dup, platform=task["platform"])
            if not dup:
                audit(request, "创建下载", f"{task['platform']} {task['target']}")
        except HTTPException as e:
            item.update(ok=False, error=e.detail)
        results.append(item)
    summary = {
        "created": sum(1 for r in results if r["ok"] and not r["duplicate"]),
        "duplicate": sum(1 for r in results if r["ok"] and r["duplicate"]),
        "failed": sum(1 for r in results if not r["ok"]),
    }
    return {"code": 0, "summary": summary, "results": results}


@app.get("/api/tasks", tags=["任务"], summary="任务列表")
def list_tasks():
    """获取所有任务摘要及实时进度 (不含完整日志)。undo_available=true 表示可撤销该任务的压缩。"""
    return {"code": 0, "data": [_with_undo(t) for t in task_manager.list_tasks()]}


@app.post("/api/tasks/clear")
def clear_finished_tasks():
    """清除所有已结束(完成/失败/取消)的任务记录"""
    return {"code": 0, "removed": task_manager.clear_finished()}


@app.get("/api/tasks/{task_id}")
def get_task_detail(task_id: str, tail: int = 300):
    """获取指定任务详情与最近 tail 行日志"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task["logs"] = task_manager.get_logs(task_id, max(1, min(tail, LOG_KEEP_LINES)))
    return {"code": 0, "data": _with_undo(task)}


@app.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str, request: Request):
    t = task_manager.get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task_manager.cancel(task_id):
        raise HTTPException(status_code=409, detail="任务已结束，无法取消")
    audit(request, "取消任务", f"#{task_id} {t['target']}")
    return {"code": 0, "msg": "已请求取消"}


@app.post("/api/tasks/{task_id}/retry")
def retry_task(task_id: str):
    """重试失败/取消的任务 (下载类任务会断点续传，已下载的集数自动跳过)"""
    old = task_manager.get_task(task_id)
    if not old:
        raise HTTPException(status_code=404, detail="任务不存在")
    if old["status"] not in ("failed", "cancelled"):
        raise HTTPException(status_code=409, detail="只有失败或已取消的任务可以重试")
    dup = task_manager.find_active(old["type"], old["target"])
    if dup:
        return {"code": 0, "msg": "已有相同的进行中任务", "duplicate": True, "task_id": dup["id"]}
    new = task_manager.create_task(old["type"], old["target"], old["platform"], old["params"])
    task_manager.submit(new["id"])
    return {"code": 0, "msg": "已重新提交", "duplicate": False, "task_id": new["id"]}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    if not task_manager.get_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task_manager.delete_task(task_id):
        raise HTTPException(status_code=409, detail="任务尚未结束，请先取消")
    return {"code": 0, "msg": "已删除"}


# ---------- 资产库 ----------

_dramas_cache: Dict[str, Any] = {"at": 0.0, "value": None}
_dramas_lock = threading.Lock()
_NON_EPISODE_SUFFIXES = (".temp.mp4", ".compressed.mp4")


def _is_image_file(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(16)
    except OSError:
        return False
    return (head[:3] == b"\xff\xd8\xff" or head[:8] == b"\x89PNG\r\n\x1a\n"
            or (head[:4] == b"RIFF" and head[8:12] == b"WEBP") or head[:4] == b"GIF8")


def _media_url(*parts: str) -> str:
    return "/media/" + "/".join(urllib.parse.quote(p) for p in parts)


def scan_dramas() -> Dict[str, Any]:
    result = []
    total_size_bytes = 0
    total_episodes_count = 0

    for plat in sorted(os.listdir(DOWNLOADS_DIR)):
        plat_dir = os.path.join(DOWNLOADS_DIR, plat)
        if not os.path.isdir(plat_dir) or plat.startswith(("_", ".")):
            continue
        try:
            items = sorted(os.listdir(plat_dir))
        except OSError:
            continue

        for item in items:
            item_dir = os.path.join(plat_dir, item)
            if item.startswith(("_", ".")) or not os.path.isdir(item_dir):
                continue

            mp4_files: List[str] = []
            folder_size = 0
            newest = 0.0
            file_names = set()
            try:
                with os.scandir(item_dir) as it:
                    for e in it:
                        if not e.is_file():
                            continue
                        st = e.stat()
                        folder_size += st.st_size
                        newest = max(newest, st.st_mtime)
                        file_names.add(e.name)
                        low = e.name.lower()
                        if low.endswith(".mp4") and not low.endswith(_NON_EPISODE_SUFFIXES):
                            mp4_files.append(e.name)
            except OSError:
                continue
            mp4_files.sort()
            total_size_bytes += folder_size
            total_episodes_count += len(mp4_files)

            poster_url = None
            for p_name in ("poster.jpg", "poster.webp", "poster.png"):
                # 按文件头校验：历史上有被反爬挑战页(HTML)冒充成 poster.jpg 的坏文件，前端会显示成破图
                if p_name in file_names and _is_image_file(os.path.join(item_dir, p_name)):
                    poster_url = _media_url(plat, item, p_name)
                    break

            meta_data: Dict[str, Any] = {}
            if "metadata.json" in file_names:
                try:
                    with open(os.path.join(item_dir, "metadata.json"), "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        meta_data = loaded
                except Exception:
                    pass

            zip_path = os.path.join(plat_dir, f"{item}.zip")
            has_zip = os.path.isfile(zip_path)
            zip_stale = has_zip and os.path.getmtime(zip_path) < newest

            result.append({
                "platform": plat,
                "folder_name": item,
                "title": meta_data.get("title") or meta_data.get("chinese_title") or item,
                "chinese_title": meta_data.get("chinese_title", ""),
                "episodes_count": len(mp4_files),
                "episodes_list": mp4_files,
                "size_mb": round(folder_size / (1024 * 1024), 2),
                "poster_url": poster_url,
                "tags": meta_data.get("tags", []) if isinstance(meta_data.get("tags", []), list) else [],
                "summary": meta_data.get("summary") or meta_data.get("description", ""),
                "has_readme": "剧集说明.md" in file_names,
                "first_episode_url": _media_url(plat, item, mp4_files[0]) if mp4_files else None,
                "has_zip": has_zip,
                "zip_stale": zip_stale,
                "zip_url": _media_url(plat, f"{item}.zip") if has_zip else None,
                "relative_path": f"{plat}/{item}",
                "updated_at": datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M") if newest else "",
            })

    return {
        "code": 0,
        "data": result,
        "stats": {
            "total_dramas": len(result),
            "total_episodes": total_episodes_count,
            "total_size_gb": round(total_size_bytes / (1024 ** 3), 2),
        },
    }


def list_all_dramas(max_age: float = 3.0) -> Dict[str, Any]:
    """扫描磁盘较慢，3 秒内的重复请求(多人同时打开页面)直接用缓存；任务结束会使缓存失效。"""
    with _dramas_lock:
        fresh = (time.time() - _dramas_cache["at"]) < max_age
        if _dramas_cache["value"] is not None and fresh and not task_manager.dramas_dirty:
            return _dramas_cache["value"]
        task_manager.dramas_dirty = False
        value = scan_dramas()
        _dramas_cache.update(at=time.time(), value=value)
        return value


@app.get("/api/dramas")
def api_list_dramas():
    """扫描并获取已下载的所有剧集列表（海报墙资产）"""
    return list_all_dramas()


def _submit_dir_task(task_type: str, rel_path: str, params: Optional[dict] = None):
    abs_path = resolve_drama_dir(rel_path)
    dup = task_manager.find_active(task_type, abs_path)
    if dup:
        return dup, True
    # 同目录正在下载/压缩时，dir_lock 会让后到的任务排队等待，不会并发改写同一批文件
    plat = os.path.basename(os.path.dirname(abs_path))
    task = task_manager.create_task(task_type, abs_path, plat, params or {})
    task_manager.submit(task["id"])
    return task, False


@app.post("/api/compress", tags=["资产库"], summary="压缩某部剧")
def manual_compress(req: CompressRequest, request: Request):
    """
    对 path ('平台目录/剧集目录') 触发压缩。keep_original=true(默认) 时原片进回收站，可撤销。
    已是 H.265 的视频自动跳过；压缩后不更小的保留原片。
    """
    task, dup = _submit_dir_task("compress", req.path, {"keep_original": req.keep_original})
    if not dup:
        audit(request, "压缩", f"{req.path} (保留原片={req.keep_original})")
    return {"code": 0, "msg": "已有相同的进行中任务" if dup else "压缩任务已提交", "duplicate": dup, "task_id": task["id"]}


@app.post("/api/zip", tags=["资产库"], summary="打包某部剧为 ZIP")
def manual_zip(req: PathRequest, request: Request):
    """手动对指定短剧目录打包为 ZIP"""
    task, dup = _submit_dir_task("zip", req.path)
    if not dup:
        audit(request, "打包ZIP", req.path)
    return {"code": 0, "msg": "已有相同的进行中任务" if dup else "打包任务已提交", "duplicate": dup, "task_id": task["id"]}


def dir_busy(abs_dir: str) -> bool:
    """该剧目录是否正被任务占用 (排队/运行中的任务目标或结果目录，或持有目录锁)。"""
    key = os.path.normcase(os.path.realpath(abs_dir))
    with task_manager.lock:
        for t in task_manager.tasks.values():
            if t["status"] not in ("pending", "running"):
                continue
            for c in [t["target"]] + list(t.get("result_dirs", [])):
                if isinstance(c, str) and os.path.isabs(c) and os.path.normcase(os.path.realpath(c)) == key:
                    return True
    return task_manager.dir_lock(abs_dir).locked()


@app.post("/api/dramas/delete", tags=["资产库"], summary="删除某部剧 (移入回收站，可恢复)")
def delete_drama(req: PathRequest, request: Request):
    """不会真正删除：整部剧(含同名 ZIP)移入回收站，保留 DL_TRASH_DAYS 天，期间可恢复。"""
    abs_path = resolve_drama_dir(req.path)
    if dir_busy(abs_path):
        raise HTTPException(status_code=409, detail="这部剧正在下载/处理中，请先取消相关任务")
    try:
        entry_id = trash.move_drama_to_trash(DOWNLOADS_DIR, abs_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"移入回收站失败 (文件可能正被播放器/资源管理器占用): {e}")
    task_manager.dramas_dirty = True
    audit(request, "删除剧集(进回收站)", req.path)
    return {"code": 0, "msg": f"已移入回收站，{TRASH_DAYS} 天内可恢复", "trash_id": entry_id, "retention_days": TRASH_DAYS}


@app.get("/api/dramas/export.csv", tags=["资产库"], summary="导出资产清单 CSV")
def export_dramas_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["平台", "剧名", "目录名", "集数", "大小(MB)", "最近更新", "有ZIP", "路径"])
    for d in list_all_dramas(max_age=0)["data"]:
        w.writerow([d["platform"], d["title"], d["folder_name"], d["episodes_count"], d["size_mb"],
                    d["updated_at"], "是" if d["has_zip"] else "否", d["relative_path"]])
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="dramas.csv"'})


def _is_local(request: Request) -> bool:
    return (request.client.host if request.client else "") in ("127.0.0.1", "::1", "localhost")


@app.post("/api/open", tags=["资产库"], summary="在服务器所在电脑上打开剧集文件夹")
def open_folder(req: PathRequest, request: Request):
    """仅限从运行平台的这台电脑本机访问时可用 (同事远程访问时返回 403)。"""
    if not _is_local(request):
        raise HTTPException(status_code=403, detail="只能在运行本平台的这台电脑上打开文件夹")
    abs_path = resolve_drama_dir(req.path)
    try:
        if os.name == "nt":
            os.startfile(abs_path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", abs_path])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开失败: {e}")
    return {"code": 0, "msg": "已打开"}


# ---------- 回收站 ----------

def restore_trash_entry(entry_id: str, request: Optional[Request] = None) -> Dict[str, Any]:
    entries = {e["id"]: e for e in trash.list_entries(DOWNLOADS_DIR, TRASH_DAYS)}
    e = entries.get(entry_id)
    if not e:
        raise HTTPException(status_code=404, detail="回收站里没有这个条目 (可能已被清理)")
    drama_dir = os.path.join(DOWNLOADS_DIR, e["platform"], e["drama"])
    if e["kind"] == "compress" and dir_busy(drama_dir):
        raise HTTPException(status_code=409, detail="这部剧正在处理中，请等任务结束后再撤销")
    try:
        m = trash.restore(DOWNLOADS_DIR, entry_id)
    except trash.TrashError as ex:
        raise HTTPException(status_code=ex.status, detail=str(ex))
    except OSError as ex:
        raise HTTPException(status_code=500, detail=f"恢复失败 (文件可能被占用): {ex}")
    task_manager.dramas_dirty = True
    audit(request, "恢复" if m["kind"] == "delete" else "撤销压缩", f"{m['platform']}/{m['drama']}")
    return m


@app.get("/api/trash", tags=["回收站"], summary="回收站列表")
def list_trash():
    entries = trash.list_entries(DOWNLOADS_DIR, TRASH_DAYS)
    return {"code": 0, "data": entries, "retention_days": TRASH_DAYS,
            "total_mb": round(sum(e["size_mb"] for e in entries), 2)}


@app.post("/api/trash/purge", tags=["回收站"], summary="永久删除回收站条目 (不可恢复，需 confirm=true)")
def purge_trash(req: PurgeRequest, request: Request):
    if not req.confirm:
        raise HTTPException(status_code=400, detail="永久删除不可恢复，请传 confirm=true 确认")
    if not req.all and not req.ids:
        raise HTTPException(status_code=400, detail="请指定 ids，或 all=true 清空回收站")
    try:
        res = trash.purge(DOWNLOADS_DIR, None if req.all else req.ids)
    except trash.TrashError as ex:
        raise HTTPException(status_code=ex.status, detail=str(ex))
    audit(request, "永久删除(回收站)", f"{'全部' if req.all else ','.join(req.ids or [])}，释放 {res['freed_mb']} MB")
    return {"code": 0, **res}


@app.post("/api/trash/{entry_id}/restore", tags=["回收站"], summary="恢复 / 撤销")
def restore_trash(entry_id: str, request: Request):
    """kind=delete 恢复被删除的剧集；kind=compress 撤销压缩 (换回原片)。"""
    m = restore_trash_entry(entry_id, request)
    return {"code": 0, "msg": "已恢复" if m["kind"] == "delete" else "已撤销压缩，换回原片", "entry": m}


@app.get("/api/audit", tags=["系统"], summary="操作记录")
def api_audit(limit: int = 50):
    return {"code": 0, "data": read_audit(limit)}


# ---------- 登录 / 健康检查 ----------

@app.post("/api/login", tags=["系统"], summary="输入访问口令 (设置了 DL_TOKEN 时)")
def login(req: LoginRequest, response: Response):
    tok = auth_token()
    if tok and not hmac.compare_digest(req.token.encode("utf-8"), tok.encode("utf-8")):
        raise HTTPException(status_code=401, detail="口令错误")
    if tok:
        response.set_cookie("dl_token", tok, httponly=True, samesite="lax", max_age=30 * 86400)
    return {"code": 0, "msg": "ok"}


@app.get("/api/health", tags=["系统"], summary="健康检查 (无需口令)")
def health(request: Request):
    return {"ok": True, "version": VERSION, "auth_required": bool(auth_token()),
            "authed": is_authed(request.headers, request.cookies)}


@app.get("/api/system", tags=["系统"], summary="运行环境信息")
def system_info(request: Request):
    """当前实际使用的编码器、并发数、磁盘剩余空间、回收站保留天数等"""
    try:
        free_gb = round(shutil.disk_usage(DOWNLOADS_DIR).free / (1024 ** 3), 1)
    except OSError:
        free_gb = None
    return {"code": 0, "data": {
        **SYSTEM_INFO,
        "version": VERSION,
        "workers": WORKERS,
        "queued": task_manager.queue.qsize(),
        "disk_free_gb": free_gb,
        "downloads_dir": DOWNLOADS_DIR,
        "trash_days": TRASH_DAYS,
        "local": _is_local(request),   # 前端据此决定是否显示“打开文件夹”
        "auth_required": bool(auth_token()),
    }}


# ==================== AI 智能助手与意图解析 ====================

_QUERY_WORDS = ("查询", "查看", "列表", "有多少", "统计", "已下载", "资产", "list")
_TASK_QUERY_WORDS = ("任务", "进度", "队列")


@app.post("/api/ai/chat")
def ai_chat(req: AIChatRequest, request: Request):
    """
    内置轻量级自然语言意图理解器 (支持同事直接发送自然指令)
    可无缝扩充接入大语言模型 (OpenAI / DeepSeek / Claude / Dify)
    """
    msg = req.message.strip()
    if not msg:
        return {"code": 0, "reply": "你好！我是短剧下载助手。你可以直接向我发送短剧链接，或者用一句话指挥我，例如：'帮我下载 https://www.slitz.com/shorts/room-service 并压缩' 或 '查询目前已下载的所有剧集'。"}

    lower = msg.lower()

    # 1. 含链接 → 下载 (必须最先判断，否则链接里的 'list' 之类字样会被误判为查询)
    url_match = re.search(r"(https?://[^\s]+)", msg)
    if url_match:
        url = url_match.group(1).rstrip(",，。；;)）")
        auto_comp = "不压缩" not in msg
        auto_zip = "zip" in lower or "压缩包" in msg or "打包" in msg
        max_eps = None
        m_eps = re.search(r"前\s*(\d+)\s*集", msg)
        if m_eps:
            max_eps = max(1, min(int(m_eps.group(1)), 999))
        try:
            task, dup = create_download(url, auto_comp, auto_zip, max_eps)
        except HTTPException as e:
            return {"code": 0, "reply": f"⚠️ 这个链接我处理不了：{e.detail}"}

        if not dup:
            audit(request, "创建下载(AI助手)", f"{task['platform']} {task['target']}")
        if dup:
            return {"code": 0, "reply": f"ℹ️ 这个链接已经有一个进行中的任务了 (任务ID: `{task['id']}`)，请在任务队列里查看进度。", "task_id": task["id"]}
        parts = [
            f"✅ 收到下载指令！已创建下载任务 (任务ID: {task['id']})",
            f"- 识别平台：{task['platform']}",
            f"- 目标链接：{url}",
            f"- 硬件加速压缩：{'开启 (QSV / HEVC)' if auto_comp else '关闭'}",
            f"- 打包 ZIP：{'开启' if auto_zip else '关闭'}",
        ]
        if max_eps:
            parts.append(f"- 限制集数：前 {max_eps} 集")
        parts.append("\n任务已进入队列，可在【任务队列】标签页查看实时进度。")
        return {"code": 0, "reply": "\n".join(parts), "task_id": task["id"]}

    # 2. ReelShort 最新剧
    if "最新" in msg and ("reelshort" in lower or "短剧" in msg):
        m_num = re.search(r"(\d+)", msg)
        num = max(1, min(int(m_num.group(1)) if m_num else 2, 10))
        task, dup = create_download(f"--latest {num}", True, False, None)
        if dup:
            return {"code": 0, "reply": f"ℹ️ 已有一个相同的批量任务在进行中 (任务ID: {task['id']})。", "task_id": task["id"]}
        return {
            "code": 0,
            "reply": f"🚀 已创建 ReelShort 批量任务：自动探测并下载最新上线的 {num} 部短剧！任务 ID：{task['id']}。",
            "task_id": task["id"],
        }

    # 回收站 / 撤销
    if "回收站" in msg or any(k in msg for k in ("撤销", "恢复", "还原")):
        entries = trash.list_entries(DOWNLOADS_DIR, TRASH_DAYS)
        if any(k in msg for k in ("撤销", "恢复", "还原")):
            if not entries:
                return {"code": 0, "reply": "回收站是空的，没有可以撤销/恢复的内容。"}
            latest = entries[0]
            try:
                restore_trash_entry(latest["id"], request)
            except HTTPException as e:
                return {"code": 0, "reply": f"⚠️ 没能撤销最近一次操作：{e.detail}"}
            what = "撤销了压缩，换回原片" if latest["kind"] == "compress" else "恢复了被删除的剧集"
            return {"code": 0, "reply": f"↩ 已{what}：{latest['platform']}/{latest['drama']}"}
        if not entries:
            return {"code": 0, "reply": "🗑 回收站是空的。"}
        lines = [f"🗑 回收站共 {len(entries)} 项 (保留 {TRASH_DAYS} 天)，最近的："]
        for e in entries[:5]:
            lines.append(f"- {'删除' if e['kind'] == 'delete' else '压缩前原片'} · {e['platform']}/{e['drama']} · {e['size_mb']} MB")
        lines.append("\n对我说“撤销”可恢复最近一项；永久清理请在网页【回收站】操作。")
        return {"code": 0, "reply": "\n".join(lines)}

    # 3. 任务进度查询
    if any(k in msg for k in _TASK_QUERY_WORDS):
        tasks = task_manager.list_tasks()
        running = [t for t in tasks if t["status"] == "running"]
        pending = [t for t in tasks if t["status"] == "pending"]
        failed = [t for t in tasks if t["status"] == "failed"]
        lines = [f"📋 当前任务：运行中 {len(running)} 个，排队 {len(pending)} 个，失败 {len(failed)} 个，共 {len(tasks)} 条记录。"]
        for t in running[:5]:
            lines.append(f"- [{t['id']}] {t['platform']} {t['current_stage']} ({t['progress']}%)")
        return {"code": 0, "reply": "\n".join(lines)}

    # 4. 资产库统计
    if any(k in lower for k in _QUERY_WORDS) or "库" in msg:
        stats = list_all_dramas()["stats"]
        return {
            "code": 0,
            "reply": f"📊 当前短剧库资产统计：\n- 已归档短剧：{stats['total_dramas']} 部\n- 总集数：{stats['total_episodes']} 集\n- 总占用空间：{stats['total_size_gb']} GB\n\n可以切换到【资产库】标签页查看具体剧目的海报与在线试看。",
        }

    return {
        "code": 0,
        "reply": "🤔 我没能在你的话里找到有效的短剧链接或明确动作。\n\n你可以试着这样对我说：\n- “下载 https://www.slitz.com/shorts/room-service”\n- “帮我把这部剧下下来并打包ZIP：https://www.reelshort.com/movie/6ab8a43a2cdfd334da0580eb”\n- “自动下载 ReelShort 最新的 2 部剧”\n- “查看已下载列表” / “现在任务进度怎么样”",
    }


# ==================== Web 前端页面 ====================

@app.get("/", response_class=HTMLResponse)
def index_page():
    index = os.path.join(WEB_DIR, "index.html")
    if not os.path.isfile(index):
        return HTMLResponse("<h3>前端文件缺失：web/index.html</h3>", status_code=500)
    return FileResponse(index, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache"})


# ==================== 启动 ====================

def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # UDP 不会真正发包，只用来选出本机出口网卡
            return s.getsockname()[0]
    except Exception:
        return "<本机局域网IP>"


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host if host != "0.0.0.0" else "", port))
            return False
        except OSError:
            return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="短剧批量下载与管理平台 Web 服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0，局域网可访问；仅本机用请传 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="监听端口 (默认: 8000)")
    args = parser.parse_args()

    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if port_in_use(args.host, args.port):
        print(f"❌ 端口 {args.port} 已被占用，平台可能已经在运行。可换端口: python web_app.py --port {args.port + 1}")
        sys.exit(1)

    print("=" * 65)
    print("🎬 短剧批量下载与协同平台正在启动...")
    print(f"👉 本地访问地址: http://127.0.0.1:{args.port}")
    if args.host == "0.0.0.0":
        print(f"👉 局域网同事访问: http://{lan_ip()}:{args.port}")
        print("⚠️  当前对局域网内所有人开放且无登录校验；如只需本机使用请加 --host 127.0.0.1")
    print(f"👉 媒体资源库挂载: {DOWNLOADS_DIR}")
    print(f"👉 并发任务数: {WORKERS}")
    print("=" * 65)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
