# -*- coding: utf-8 -*-
"""
回收站：让“删除剧集”和“压缩替换原片”都可以撤销。

布局 (都在 downloads/_trash/ 下；以 _ 开头的目录不会出现在资产库，也不会被压缩/扫描)：
    _trash/<id>/manifest.json   元数据
    _trash/<id>/files/          kind=compress：被替换前的原片 (保持相对剧集目录的子路径)
    _trash/<id>/dir/            kind=delete：整部剧的目录
    _trash/<id>/zip/            kind=delete：同名 ZIP (如果有)

本模块只做文件操作，不依赖 Web 框架；调用方负责并发保护(任务互斥)。
"""
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

TRASH_NAME = "_trash"
DEFAULT_RETENTION_DAYS = 7


class TrashError(Exception):
    """可直接展示给用户的错误；status 对应建议的 HTTP 状态码。"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def trash_root(downloads_dir: str) -> str:
    return os.path.join(downloads_dir, TRASH_NAME)


def _entry_dir(downloads_dir: str, entry_id: str) -> str:
    # entry_id 来自用户请求，必须是单一路径分量
    if not entry_id or entry_id != os.path.basename(entry_id) or entry_id.startswith("."):
        raise TrashError("非法的回收站条目 ID", 400)
    return os.path.join(trash_root(downloads_dir), entry_id)


def _now() -> datetime:
    return datetime.now()


def _dir_stats(path: str):
    size = files = 0
    for root, _, names in os.walk(path):
        for n in names:
            try:
                size += os.path.getsize(os.path.join(root, n))
                files += 1
            except OSError:
                pass
    return size, files


def _write_manifest(entry_path: str, manifest: Dict[str, Any]):
    tmp = os.path.join(entry_path, "manifest.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(entry_path, "manifest.json"))


def _read_manifest(entry_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(os.path.join(entry_path, "manifest.json"), "r", encoding="utf-8") as f:
            m = json.load(f)
        return m if isinstance(m, dict) else None
    except Exception:
        return None


def _new_entry(downloads_dir: str, kind: str, platform: str, drama: str, note: str = "") -> (str, str, Dict[str, Any]):
    entry_id = f"{_now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"
    path = _entry_dir(downloads_dir, entry_id)
    os.makedirs(path, exist_ok=True)
    manifest = {
        "id": entry_id, "kind": kind, "platform": platform, "drama": drama,
        "created_at": _now().strftime("%Y-%m-%d %H:%M:%S"), "note": note,
    }
    _write_manifest(path, manifest)
    return entry_id, path, manifest


# ---------- 压缩前原片 ----------

def begin_compress_backup(downloads_dir: str, platform: str, drama: str) -> (str, str):
    """压缩开始前创建条目，返回 (entry_id, 传给 compress_tool --backup-dir 的目录)。"""
    entry_id, path, _ = _new_entry(downloads_dir, "compress", platform, drama, "压缩前的原片")
    files_dir = os.path.join(path, "files")
    os.makedirs(files_dir, exist_ok=True)
    return entry_id, files_dir


def finalize_compress_backup(downloads_dir: str, entry_id: str) -> bool:
    """压缩结束后调用：没有任何原片被替换(全部跳过/失败)就丢弃空条目。返回条目是否保留。"""
    path = _entry_dir(downloads_dir, entry_id)
    _, files = _dir_stats(os.path.join(path, "files"))
    if files == 0:
        shutil.rmtree(path, ignore_errors=True)
        return False
    return True


# ---------- 删除剧集 ----------

def move_drama_to_trash(downloads_dir: str, drama_dir: str) -> str:
    """把整部剧(及同名 ZIP)移入回收站。返回 entry_id。"""
    drama_dir = os.path.abspath(drama_dir)
    platform = os.path.basename(os.path.dirname(drama_dir))
    drama = os.path.basename(drama_dir)
    entry_id, path, _ = _new_entry(downloads_dir, "delete", platform, drama, "已删除的剧集")
    try:
        shutil.move(drama_dir, os.path.join(path, "dir"))
        zip_path = drama_dir + ".zip"
        if os.path.isfile(zip_path):
            os.makedirs(os.path.join(path, "zip"), exist_ok=True)
            shutil.move(zip_path, os.path.join(path, "zip", os.path.basename(zip_path)))
    except Exception:
        # 移动失败：尽量还原，并清掉条目，避免留下半截状态
        dir_in_trash = os.path.join(path, "dir")
        if os.path.isdir(dir_in_trash) and not os.path.exists(drama_dir):
            shutil.move(dir_in_trash, drama_dir)
        shutil.rmtree(path, ignore_errors=True)
        raise
    return entry_id


# ---------- 查询 / 恢复 / 清理 ----------

def list_entries(downloads_dir: str, retention_days: int = DEFAULT_RETENTION_DAYS) -> List[Dict[str, Any]]:
    root = trash_root(downloads_dir)
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root), reverse=True):
        path = os.path.join(root, name)
        m = _read_manifest(path) if os.path.isdir(path) else None
        if not m:
            continue
        size, files = _dir_stats(path)
        try:
            created = datetime.strptime(m["created_at"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            created = datetime.fromtimestamp(os.path.getmtime(path))
        expires = created + timedelta(days=retention_days)
        out.append({
            **m,
            "size_mb": round(size / (1024 * 1024), 2),
            "file_count": files - 1 if files else 0,  # 不计 manifest.json 本身
            "expires_at": expires.strftime("%Y-%m-%d %H:%M:%S"),
            "days_left": max(0, (expires - _now()).days),
        })
    return out


def restore(downloads_dir: str, entry_id: str) -> Dict[str, Any]:
    """恢复条目。冲突/目录不存在抛 TrashError(409/404)。返回条目 manifest。"""
    path = _entry_dir(downloads_dir, entry_id)
    m = _read_manifest(path) if os.path.isdir(path) else None
    if not m:
        raise TrashError("回收站里没有这个条目 (可能已被清理)", 404)

    plat_dir = os.path.join(downloads_dir, m["platform"])
    drama_dir = os.path.join(plat_dir, m["drama"])

    if m["kind"] == "delete":
        if os.path.exists(drama_dir):
            raise TrashError("同名剧集目录已存在，无法恢复。请先处理现有目录", 409)
        os.makedirs(plat_dir, exist_ok=True)
        shutil.move(os.path.join(path, "dir"), drama_dir)
        zips = os.path.join(path, "zip")
        if os.path.isdir(zips):
            for z in os.listdir(zips):
                dst = os.path.join(plat_dir, z)
                if not os.path.exists(dst):
                    shutil.move(os.path.join(zips, z), dst)
    elif m["kind"] == "compress":
        if not os.path.isdir(drama_dir):
            raise TrashError("原剧集目录已不存在，无法撤销压缩 (可先恢复被删除的剧集)", 409)
        files_dir = os.path.join(path, "files")
        for root, _, names in os.walk(files_dir):
            for n in names:
                src = os.path.join(root, n)
                dst = os.path.join(drama_dir, os.path.relpath(src, files_dir))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.replace(src, dst)  # 覆盖压缩后的版本，换回原片
    else:
        raise TrashError("未知的条目类型", 400)

    shutil.rmtree(path, ignore_errors=True)
    return m


def purge(downloads_dir: str, entry_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """永久删除。entry_ids 为 None 表示清空整个回收站。返回 {removed, freed_mb}。"""
    root = trash_root(downloads_dir)
    if entry_ids is None:
        entry_ids = [e["id"] for e in list_entries(downloads_dir)]
    removed = 0
    freed = 0
    for eid in entry_ids:
        path = _entry_dir(downloads_dir, eid)
        if not os.path.isdir(path):
            continue
        size, _ = _dir_stats(path)
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.exists(path):
            removed += 1
            freed += size
    return {"removed": removed, "freed_mb": round(freed / (1024 * 1024), 2)}


def purge_expired(downloads_dir: str, retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    """清理超过保留期的条目，返回清理数量。"""
    cutoff = _now() - timedelta(days=retention_days)
    expired = []
    for e in list_entries(downloads_dir, retention_days):
        try:
            if datetime.strptime(e["created_at"], "%Y-%m-%d %H:%M:%S") < cutoff:
                expired.append(e["id"])
        except Exception:
            pass
    return purge(downloads_dir, expired)["removed"] if expired else 0
