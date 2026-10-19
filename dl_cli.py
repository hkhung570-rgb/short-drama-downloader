#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载平台命令行 (给 AI Agent / 脚本用)：所有输出都是 JSON，便于程序解析。需要平台已启动。

  python dl_cli.py status                                   # 平台是否在线、编码器、磁盘、并发
  python dl_cli.py add URL [URL ...] [--zip] [--no-compress] [--keep-original] [--max-eps N]
  python dl_cli.py tasks [--status running]                 # 任务列表(精简)
  python dl_cli.py task ID [--logs 30]                      # 单个任务详情 + 最近日志
  python dl_cli.py wait ID [--timeout 600]                  # 阻塞到任务结束
  python dl_cli.py cancel ID | retry ID
  python dl_cli.py dramas [--search 关键词] [--platform Slitz短剧] [--limit 50]
  python dl_cli.py compress "Slitz短剧/room-service" [--no-keep-original]
  python dl_cli.py zip "Slitz短剧/room-service"
  python dl_cli.py delete "Slitz短剧/room-service"          # 移入回收站，可恢复
  python dl_cli.py trash                                    # 回收站列表
  python dl_cli.py restore ENTRY_ID                         # 恢复被删除的剧 / 撤销压缩
  python dl_cli.py purge --ids ID [ID ...] --yes            # 永久删除(不可恢复)，必须带 --yes
  python dl_cli.py purge --all --yes
  python dl_cli.py audit [--limit 30]

环境变量: DL_URL (默认 http://127.0.0.1:8000)  DL_TOKEN (平台设置了口令时)  DL_OPERATOR (默认 agent)
退出码: 0 成功 · 1 平台返回错误 · 2 连不上平台/参数错误 · 3 wait 时任务失败/取消/超时
"""
import argparse
import json
import sys

from dl_client import Client, DLError, TERMINAL

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def brief_task(t):
    keys = ("id", "type", "platform", "target", "status", "progress", "current_stage", "error", "warning",
            "result_dirs", "undo_available", "trash_ids", "created_at", "finished_at")
    return {k: t.get(k) for k in keys}


def brief_drama(d):
    return {"path": d["relative_path"], "title": d["title"], "episodes": d["episodes_count"],
            "size_mb": d["size_mb"], "has_zip": d["has_zip"], "zip_stale": d.get("zip_stale", False),
            "updated_at": d.get("updated_at", "")}


def build_parser():
    p = argparse.ArgumentParser(description="下载平台命令行 (JSON 输出)", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")

    a = sub.add_parser("add")
    a.add_argument("urls", nargs="+")
    a.add_argument("--zip", action="store_true", help="下载后打包 ZIP")
    a.add_argument("--no-compress", action="store_true", help="不自动压缩")
    a.add_argument("--keep-original", action="store_true", help="自动压缩时把原片留在回收站(可撤销，多占空间)")
    a.add_argument("--max-eps", type=int)

    t = sub.add_parser("tasks")
    t.add_argument("--status", choices=["pending", "running", "completed", "failed", "cancelled"])
    t.add_argument("--full", action="store_true")

    for name in ("task", "wait", "cancel", "retry"):
        x = sub.add_parser(name)
        x.add_argument("id")
        if name == "task":
            x.add_argument("--logs", type=int, default=30)
        if name == "wait":
            x.add_argument("--timeout", type=float, default=600)

    d = sub.add_parser("dramas")
    d.add_argument("--search")
    d.add_argument("--platform")
    d.add_argument("--limit", type=int, default=50)
    d.add_argument("--full", action="store_true")

    c = sub.add_parser("compress")
    c.add_argument("path")
    c.add_argument("--no-keep-original", action="store_true", help="不保留原片(省空间，但不可撤销)")

    for name in ("zip", "delete"):
        sub.add_parser(name).add_argument("path")

    sub.add_parser("trash")
    sub.add_parser("restore").add_argument("id")

    pg = sub.add_parser("purge")
    pg.add_argument("--ids", nargs="+")
    pg.add_argument("--all", action="store_true")
    pg.add_argument("--yes", action="store_true", help="确认永久删除(不可恢复)")

    sub.add_parser("audit").add_argument("--limit", type=int, default=30)
    return p


def run(args, c: Client):
    cmd = args.cmd
    if cmd == "status":
        h = c.health()
        return 0, {**h, "system": c.system() if h.get("authed") else None}
    if cmd == "add":
        return 0, c.add(args.urls, auto_compress=not args.no_compress, auto_zip=args.zip,
                        keep_original=args.keep_original, max_eps=args.max_eps)
    if cmd == "tasks":
        ts = c.tasks(args.status)
        return 0, [t if args.full else brief_task(t) for t in ts]
    if cmd == "task":
        t = c.task(args.id, args.logs)
        return 0, {**brief_task(t), "logs": t.get("logs", [])}
    if cmd == "wait":
        t = c.wait(args.id, timeout=args.timeout)
        ok = t["status"] == "completed"
        return (0 if ok else 3), {**brief_task(t), "timed_out": t.get("timed_out", False), "logs": t.get("logs", [])}
    if cmd == "cancel":
        return 0, c.cancel(args.id)
    if cmd == "retry":
        return 0, c.retry(args.id)
    if cmd == "dramas":
        res = c.dramas(args.search, args.platform)
        items = res["data"][: args.limit]
        return 0, {"stats": res["stats"], "matched": len(res["data"]), "returned": len(items),
                   "data": items if args.full else [brief_drama(d) for d in items]}
    if cmd == "compress":
        return 0, c.compress(args.path, keep_original=not args.no_keep_original)
    if cmd == "zip":
        return 0, c.zip(args.path)
    if cmd == "delete":
        return 0, c.delete_drama(args.path)
    if cmd == "trash":
        return 0, c.trash()
    if cmd == "restore":
        return 0, c.restore(args.id)
    if cmd == "purge":
        if not args.yes:
            return 2, {"error": "永久删除不可恢复，请加 --yes 确认"}
        if not args.all and not args.ids:
            return 2, {"error": "请用 --ids 指定条目，或 --all 清空回收站"}
        return 0, c.purge(ids=args.ids, all=args.all, confirm=True)
    if cmd == "audit":
        return 0, c.audit(args.limit)
    return 2, {"error": f"未知命令 {cmd}"}


def main(argv=None):
    args = build_parser().parse_args(argv)
    c = Client()
    try:
        code, payload = run(args, c)
    except DLError as e:
        out({"error": e.message, "status": e.status})
        return 2 if e.status == 0 else 1
    out(payload)
    return code


if __name__ == "__main__":
    sys.exit(main())
