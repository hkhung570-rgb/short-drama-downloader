# -*- coding: utf-8 -*-
"""
下载平台的 Python 客户端 (纯标准库，无第三方依赖)。CLI(dl_cli.py) 和 MCP 服务器(mcp_server.py) 都基于它；
也可以直接在你的脚本/Agent 里用：

    from dl_client import Client
    c = Client()                                   # 默认 http://127.0.0.1:8000
    r = c.add(["https://www.slitz.com/shorts/room-service"])
    c.wait(r["results"][0]["task_id"], timeout=1800)

环境变量: DL_URL (默认 http://127.0.0.1:8000)、DL_TOKEN (平台设置了口令时)、DL_OPERATOR (操作记录里显示的名字，默认 agent)
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

__version__ = "2.2.0"

TERMINAL = ("completed", "failed", "cancelled")


class DLError(Exception):
    """平台返回的错误。status=0 表示连不上平台。"""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class Client:
    def __init__(self, base: Optional[str] = None, token: Optional[str] = None,
                 operator: Optional[str] = None, timeout: float = 30):
        self.base = (base or os.environ.get("DL_URL") or "http://127.0.0.1:8000").rstrip("/")
        self.token = token if token is not None else os.environ.get("DL_TOKEN", "")
        self.operator = operator or os.environ.get("DL_OPERATOR") or "agent"
        self.timeout = timeout

    # ---------- 底层 ----------
    def _request(self, method: str, path: str, body: Any = None) -> Dict[str, Any]:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"X-Operator": urllib.parse.quote(self.operator), "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            msg = ""
            try:
                detail = json.loads(e.read().decode("utf-8")).get("detail")
                msg = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
            except Exception:
                pass
            if e.code == 401:
                msg = (msg or "需要访问口令") + "（请设置环境变量 DL_TOKEN）"
            raise DLError(e.code, msg or f"HTTP {e.code}")
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
            raise DLError(0, f"无法连接下载平台 {self.base}：{getattr(e, 'reason', e)}。请先启动平台（双击 启动下载平台.bat）")

    # ---------- 系统 ----------
    def health(self):
        return self._request("GET", "/api/health")

    def system(self):
        return self._request("GET", "/api/system")["data"]

    # ---------- 任务 ----------
    def add(self, urls: List[str], auto_compress: bool = True, auto_zip: bool = False,
            keep_original: bool = False, max_eps: Optional[int] = None):
        return self._request("POST", "/api/tasks/batch", {
            "urls": urls, "auto_compress": auto_compress, "auto_zip": auto_zip,
            "keep_original": keep_original, "max_eps": max_eps})

    def tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self._request("GET", "/api/tasks")["data"]
        return [t for t in data if not status or t["status"] == status]

    def task(self, task_id: str, tail: int = 30) -> Dict[str, Any]:
        return self._request("GET", f"/api/tasks/{urllib.parse.quote(task_id)}?tail={int(tail)}")["data"]

    def cancel(self, task_id: str):
        return self._request("POST", f"/api/tasks/{urllib.parse.quote(task_id)}/cancel")

    def retry(self, task_id: str):
        return self._request("POST", f"/api/tasks/{urllib.parse.quote(task_id)}/retry")

    def wait(self, task_id: str, timeout: float = 600, interval: float = 2) -> Dict[str, Any]:
        """阻塞到任务结束或超时。超时返回当前状态并带 timed_out=True (任务仍在后台继续)。"""
        end = time.time() + timeout
        while True:
            t = self.task(task_id, tail=10)
            if t["status"] in TERMINAL:
                return t
            if time.time() >= end:
                t["timed_out"] = True
                return t
            time.sleep(interval)

    # ---------- 资产库 ----------
    def dramas(self, search: Optional[str] = None, platform: Optional[str] = None):
        res = self._request("GET", "/api/dramas")
        data = res["data"]
        if platform:
            data = [d for d in data if d["platform"].lower() == platform.lower()]
        if search:
            q = search.lower()
            data = [d for d in data if q in (d["title"] + " " + d["chinese_title"] + " " + d["folder_name"]).lower()]
        return {"stats": res["stats"], "data": data}

    def compress(self, path: str, keep_original: bool = True):
        return self._request("POST", "/api/compress", {"path": path, "keep_original": keep_original})

    def zip(self, path: str):
        return self._request("POST", "/api/zip", {"path": path})

    def delete_drama(self, path: str):
        """不会真删：移入回收站，可用 restore 恢复。"""
        return self._request("POST", "/api/dramas/delete", {"path": path})

    # ---------- 回收站 / 记录 ----------
    def trash(self):
        return self._request("GET", "/api/trash")

    def restore(self, entry_id: str):
        return self._request("POST", f"/api/trash/{urllib.parse.quote(entry_id)}/restore")

    def purge(self, ids: Optional[List[str]] = None, all: bool = False, confirm: bool = False):
        """永久删除，不可恢复；必须 confirm=True。"""
        return self._request("POST", "/api/trash/purge", {"ids": ids, "all": all, "confirm": confirm})

    def audit(self, limit: int = 30):
        return self._request("GET", f"/api/audit?limit={int(limit)}")["data"]
