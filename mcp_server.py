#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP (Model Context Protocol) 服务器：让 Claude Desktop / Claude Code / 其他支持 MCP 的 AI Agent 直接调用下载平台。
纯标准库实现 (stdio, 按行 JSON-RPC)，无需安装 mcp SDK。它只是下载平台 HTTP API 的薄封装，平台需要已在运行。

配置示例 (Claude Desktop 的 claude_desktop_config.json，或项目 .mcp.json)：
{
  "mcpServers": {
    "short-drama": {
      "command": "python",
      "args": ["C:/Projects/下载工具/mcp_server.py"],
      "env": { "DL_URL": "http://127.0.0.1:8000", "DL_TOKEN": "", "DL_OPERATOR": "claude" }
    }
  }
}
"""
import json
import sys
import traceback

from dl_client import Client, DLError, __version__

for _s in (sys.stdin, sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROTOCOL_DEFAULT = "2024-11-05"


def _obj(props=None, required=None):
    return {"type": "object", "properties": props or {}, "required": required or []}


TOOLS = [
    {"name": "system_status", "description": "查看下载平台是否在线、当前编码器、磁盘剩余空间、并发数。",
     "inputSchema": _obj()},
    {"name": "add_downloads",
     "description": "创建下载任务。urls 为剧集详情页链接(支持 ReelShort / Slitz / 黄果短剧)，也可传 '--latest 2' 下载 ReelShort 最新 2 部。"
                    "同一链接已有进行中任务时不会重复创建。返回每个链接的 task_id 或失败原因。",
     "inputSchema": _obj({
         "urls": {"type": "array", "items": {"type": "string"}, "description": "链接列表，最多 50 个"},
         "auto_compress": {"type": "boolean", "description": "下载后自动压缩为 H.265，默认 true"},
         "auto_zip": {"type": "boolean", "description": "下载后自动打包 ZIP，默认 false"},
         "keep_original": {"type": "boolean", "description": "自动压缩时把原片留在回收站以便撤销(多占空间)，默认 false"},
         "max_eps": {"type": "integer", "description": "限制集数(仅 ReelShort)"}}, ["urls"])},
    {"name": "list_tasks", "description": "列出任务及进度。可按状态过滤。",
     "inputSchema": _obj({"status": {"type": "string", "enum": ["pending", "running", "completed", "failed", "cancelled"]}})},
    {"name": "get_task", "description": "查看单个任务详情和最近日志(排查失败原因)。",
     "inputSchema": _obj({"id": {"type": "string"}, "log_lines": {"type": "integer", "description": "默认 30"}}, ["id"])},
    {"name": "wait_task",
     "description": "等待任务结束(最多 timeout 秒，上限 300)。超时返回 timed_out=true，任务仍在后台继续，可稍后再次调用。",
     "inputSchema": _obj({"id": {"type": "string"}, "timeout": {"type": "number", "description": "秒，默认 120"}}, ["id"])},
    {"name": "cancel_task", "description": "取消排队/运行中的任务(已下载内容保留)。", "inputSchema": _obj({"id": {"type": "string"}}, ["id"])},
    {"name": "retry_task", "description": "重试失败/已取消的任务，下载类任务会断点续传。", "inputSchema": _obj({"id": {"type": "string"}}, ["id"])},
    {"name": "list_dramas",
     "description": "列出资产库里已下载的剧。返回 path (形如 '平台/剧目录')，其他工具用它定位剧。",
     "inputSchema": _obj({"search": {"type": "string"}, "platform": {"type": "string"},
                          "limit": {"type": "integer", "description": "默认 50"}})},
    {"name": "compress_drama",
     "description": "压缩一部剧(H.265)。已是 H.265 的自动跳过，压缩后不更小的保留原片。keep_original 默认 true：原片进回收站，可用 restore_trash 撤销。",
     "inputSchema": _obj({"path": {"type": "string"}, "keep_original": {"type": "boolean"}}, ["path"])},
    {"name": "zip_drama", "description": "把一部剧打包成 ZIP。", "inputSchema": _obj({"path": {"type": "string"}}, ["path"])},
    {"name": "delete_drama",
     "description": "删除一部剧——但只是移入回收站(保留若干天)，可用 restore_trash 恢复。执行前建议先向用户确认。",
     "inputSchema": _obj({"path": {"type": "string"}}, ["path"])},
    {"name": "list_trash", "description": "查看回收站(被删除的剧、压缩前的原片)。", "inputSchema": _obj()},
    {"name": "restore_trash",
     "description": "恢复回收站条目：kind=delete 恢复被删除的剧；kind=compress 撤销压缩(换回原片)。",
     "inputSchema": _obj({"id": {"type": "string"}}, ["id"])},
    {"name": "purge_trash",
     "description": "【不可恢复】永久删除回收站条目。必须 confirm=true，且务必先得到用户明确同意。",
     "inputSchema": _obj({"ids": {"type": "array", "items": {"type": "string"}}, "all": {"type": "boolean"},
                          "confirm": {"type": "boolean"}}, ["confirm"])},
]


def _brief_task(t):
    keys = ("id", "type", "platform", "target", "status", "progress", "current_stage", "error", "warning",
            "result_dirs", "undo_available", "trash_ids", "created_at", "finished_at")
    return {k: t.get(k) for k in keys}


def call_tool(c: Client, name: str, a: dict):
    if name == "system_status":
        h = c.health()
        return {**h, "system": c.system() if h.get("authed") else None}
    if name == "add_downloads":
        return c.add(a["urls"], a.get("auto_compress", True), a.get("auto_zip", False),
                     a.get("keep_original", False), a.get("max_eps"))
    if name == "list_tasks":
        return [_brief_task(t) for t in c.tasks(a.get("status"))]
    if name == "get_task":
        t = c.task(a["id"], int(a.get("log_lines", 30)))
        return {**_brief_task(t), "logs": t.get("logs", [])}
    if name == "wait_task":
        t = c.wait(a["id"], timeout=min(float(a.get("timeout", 120)), 300))
        return {**_brief_task(t), "timed_out": t.get("timed_out", False)}
    if name == "cancel_task":
        return c.cancel(a["id"])
    if name == "retry_task":
        return c.retry(a["id"])
    if name == "list_dramas":
        res = c.dramas(a.get("search"), a.get("platform"))
        items = res["data"][: int(a.get("limit", 50))]
        return {"stats": res["stats"], "matched": len(res["data"]), "data": [
            {"path": d["relative_path"], "title": d["title"], "episodes": d["episodes_count"],
             "size_mb": d["size_mb"], "has_zip": d["has_zip"]} for d in items]}
    if name == "compress_drama":
        return c.compress(a["path"], a.get("keep_original", True))
    if name == "zip_drama":
        return c.zip(a["path"])
    if name == "delete_drama":
        return c.delete_drama(a["path"])
    if name == "list_trash":
        return c.trash()
    if name == "restore_trash":
        return c.restore(a["id"])
    if name == "purge_trash":
        if not a.get("confirm"):
            raise DLError(400, "永久删除不可恢复，请传 confirm=true (并先征得用户同意)")
        return c.purge(a.get("ids"), bool(a.get("all", False)), True)
    raise DLError(400, f"未知工具: {name}")


def handle(msg: dict, c: Client):
    """处理一条 JSON-RPC 消息；通知(无 id)返回 None。"""
    method = msg.get("method")
    mid = msg.get("id")
    if mid is None:
        return None  # notifications/initialized 等通知不需要回复

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}

    if method == "initialize":
        proto = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL_DEFAULT
        return ok({"protocolVersion": proto, "capabilities": {"tools": {}},
                   "serverInfo": {"name": "short-drama-downloader", "version": __version__}})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        try:
            result = call_tool(c, name, args)
            return ok({"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]})
        except DLError as e:
            return ok({"isError": True, "content": [{"type": "text", "text": f"{e.message} (HTTP {e.status})"}]})
        except KeyError as e:
            return ok({"isError": True, "content": [{"type": "text", "text": f"缺少参数: {e}"}]})
        except Exception as e:
            print(traceback.format_exc(), file=sys.stderr)
            return ok({"isError": True, "content": [{"type": "text", "text": f"内部错误: {e}"}]})
    return err(-32601, f"Method not found: {method}")


def main():
    c = Client()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                         "error": {"code": -32700, "message": "Parse error"}}) + "\n")
            sys.stdout.flush()
            continue
        resp = handle(msg, c)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
