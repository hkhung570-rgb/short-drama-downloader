# -*- coding: utf-8 -*-
"""AI Agent 接入层测试：Python 客户端、命令行(JSON 输出+退出码)、MCP 服务器(stdio JSON-RPC)，全部对真实的平台子进程。"""
import json
import os
import queue
import subprocess
import sys
import threading
import time
import unittest

from _env import ROOT, live_server, make_video
from dl_client import Client, DLError


def make_drama(dl, name, files=1):
    d = os.path.join(dl, "Slitz短剧", name)
    os.makedirs(d, exist_ok=True)
    for i in range(1, files + 1):
        with open(os.path.join(d, f"第{i:02d}集.mp4"), "wb") as f:
            f.write(os.urandom(2048))
    return d


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.dl = live_server()
        cls.c = Client(cls.base, operator="pytest-agent")

    def test_health_system(self):
        h = self.c.health()
        self.assertTrue(h["ok"])
        self.assertFalse(h["auth_required"])
        s = self.c.system()
        self.assertIn("trash_days", s)
        self.assertTrue(s["local"])  # 子进程在本机，回环访问

    def test_errors_are_mapped(self):
        with self.assertRaises(DLError) as cm:
            self.c.task("nope1234")
        self.assertEqual(cm.exception.status, 404)
        self.assertIn("任务不存在", cm.exception.message)
        with self.assertRaises(DLError) as cm:
            self.c.compress("../..")
        self.assertEqual(cm.exception.status, 400)
        with self.assertRaises(DLError) as cm:
            self.c.purge(ids=["x"], confirm=False)
        self.assertEqual(cm.exception.status, 400)

    def test_unreachable_platform_gives_actionable_error(self):
        with self.assertRaises(DLError) as cm:
            Client("http://127.0.0.1:9", timeout=2).health()
        self.assertEqual(cm.exception.status, 0)
        self.assertIn("启动", cm.exception.message)

    def test_add_failing_task_wait_and_retry(self):
        # 不存在的 Slitz 标识符：探测会 404 → 任务失败；不会写入任何文件
        r = self.c.add(["zz-agent-no-such-drama-qq"], auto_compress=False)
        self.assertEqual(r["summary"]["created"], 1)
        tid = r["results"][0]["task_id"]
        t = self.c.wait(tid, timeout=90, interval=0.5)
        self.assertEqual(t["status"], "failed")
        self.assertIn("重试", t["error"])
        r2 = self.c.retry(tid)
        self.assertNotEqual(r2["task_id"], tid)
        self.c.cancel(r2["task_id"]) if self.c.task(r2["task_id"])["status"] in ("pending", "running") else None

    def test_dramas_search_and_operator_in_audit(self):
        make_drama(self.dl, "agent-search-me")
        res = self.c.dramas(search="agent-search")
        self.assertEqual([d["folder_name"] for d in res["data"]], ["agent-search-me"])
        self.c.delete_drama("Slitz短剧/agent-search-me")
        recs = self.c.audit(10)
        self.assertTrue(any(r["operator"] == "pytest-agent" and r["action"].startswith("删除剧集") for r in recs))


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.dl = live_server()

    def cli(self, *args):
        env = dict(os.environ, DL_URL=self.base, PYTHONUTF8="1")
        p = subprocess.run([sys.executable, os.path.join(ROOT, "dl_cli.py"), *args], cwd=ROOT, env=env,
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
        try:
            data = json.loads(p.stdout)
        except Exception:
            self.fail(f"CLI 输出不是 JSON: stdout={p.stdout!r} stderr={p.stderr!r}")
        return p.returncode, data

    def test_status_json(self):
        rc, d = self.cli("status")
        self.assertEqual(rc, 0)
        self.assertTrue(d["ok"])
        self.assertIn("encoder_desc", d["system"])

    def test_dramas_brief_and_limit(self):
        make_drama(self.dl, "cli-brief-1")
        make_drama(self.dl, "cli-brief-2")
        rc, d = self.cli("dramas", "--search", "cli-brief", "--limit", "1")
        self.assertEqual(rc, 0)
        self.assertEqual((d["matched"], d["returned"]), (2, 1))
        self.assertEqual(set(d["data"][0]), {"path", "title", "episodes", "size_mb", "has_zip", "zip_stale", "updated_at"})

    def test_delete_trash_restore_flow(self):
        make_drama(self.dl, "cli-flow")
        rc, d = self.cli("delete", "Slitz短剧/cli-flow")
        self.assertEqual(rc, 0)
        eid = d["trash_id"]
        rc, d = self.cli("trash")
        self.assertTrue(any(e["id"] == eid for e in d["data"]))
        rc, d = self.cli("restore", eid)
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isdir(os.path.join(self.dl, "Slitz短剧", "cli-flow")))

    def test_purge_needs_yes_and_target(self):
        rc, d = self.cli("purge", "--all")
        self.assertEqual(rc, 2)
        self.assertIn("--yes", d["error"])
        rc, d = self.cli("purge", "--yes")
        self.assertEqual(rc, 2)

    def test_api_error_exit_code_1_and_unreachable_exit_code_2(self):
        rc, d = self.cli("task", "nope1234")
        self.assertEqual(rc, 1)
        self.assertEqual(d["status"], 404)
        env = dict(os.environ, DL_URL="http://127.0.0.1:9", PYTHONUTF8="1")
        p = subprocess.run([sys.executable, os.path.join(ROOT, "dl_cli.py"), "status"], cwd=ROOT, env=env,
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(p.returncode, 2)

    def test_wait_exit_code_3_on_failed_task(self):
        rc, d = self.cli("add", "zz-cli-no-such-drama-qq", "--no-compress")
        tid = d["results"][0]["task_id"]
        rc, d = self.cli("wait", tid, "--timeout", "90")
        self.assertEqual(rc, 3)
        self.assertEqual(d["status"], "failed")


class McpClient:
    """极简 MCP 客户端：向子进程写 JSON-RPC 行，读响应行。"""

    def __init__(self, base):
        env = dict(os.environ, DL_URL=base, DL_OPERATOR="mcp-test", PYTHONUTF8="1")
        self.p = subprocess.Popen([sys.executable, os.path.join(ROOT, "mcp_server.py")], cwd=ROOT, env=env,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding="utf-8")
        self.q = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()
        self.n = 0

    def _pump(self):
        for line in self.p.stdout:
            self.q.put(line)

    def send(self, obj):
        self.p.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def request(self, method, params=None, timeout=60):
        self.n += 1
        self.send({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}})
        msg = json.loads(self.q.get(timeout=timeout))
        assert msg["id"] == self.n, msg
        return msg

    def call(self, name, **args):
        r = self.request("tools/call", {"name": name, "arguments": args})["result"]
        text = r["content"][0]["text"]
        return r.get("isError", False), text

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()
        for f in (self.p.stdout, self.p.stderr):
            try:
                f.close()
            except Exception:
                pass


class McpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.dl = live_server()
        cls.m = McpClient(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.m.close()

    def test_handshake_and_tool_list(self):
        init = self.m.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                              "clientInfo": {"name": "t", "version": "0"}})["result"]
        self.assertEqual(init["protocolVersion"], "2025-03-26")
        self.assertIn("tools", init["capabilities"])
        self.m.send({"jsonrpc": "2.0", "method": "notifications/initialized"})  # 通知：不应有回复
        tools = self.m.request("tools/list")["result"]["tools"]
        names = {t["name"] for t in tools}
        self.assertTrue({"add_downloads", "wait_task", "delete_drama", "restore_trash", "purge_trash", "list_dramas"} <= names)
        for t in tools:
            self.assertEqual(t["inputSchema"]["type"], "object")
            self.assertTrue(t["description"])
        self.assertTrue(self.m.q.empty())  # 通知没有产生多余输出

    def test_ping_and_unknown_method(self):
        self.assertEqual(self.m.request("ping")["result"], {})
        self.assertEqual(self.m.request("nonsense/method")["error"]["code"], -32601)

    def test_tool_calls(self):
        err, text = self.m.call("system_status")
        self.assertFalse(err)
        self.assertTrue(json.loads(text)["ok"])

        make_drama(self.dl, "mcp-demo")
        err, text = self.m.call("list_dramas", search="mcp-demo")
        self.assertFalse(err)
        self.assertEqual(json.loads(text)["data"][0]["path"], "Slitz短剧/mcp-demo")

        err, text = self.m.call("delete_drama", path="Slitz短剧/mcp-demo")
        self.assertFalse(err)
        eid = json.loads(text)["trash_id"]
        err, text = self.m.call("restore_trash", id=eid)
        self.assertFalse(err)
        self.assertTrue(os.path.isdir(os.path.join(self.dl, "Slitz短剧", "mcp-demo")))

    def test_error_paths_are_reported_not_crashed(self):
        err, text = self.m.call("purge_trash", all=True)               # 缺 confirm
        self.assertTrue(err)
        self.assertIn("confirm", text)
        err, text = self.m.call("compress_drama", path="../..")        # 平台拒绝
        self.assertTrue(err)
        self.assertIn("400", text)
        err, text = self.m.call("no_such_tool")
        self.assertTrue(err)
        err, text = self.m.call("get_task")                            # 缺参数
        self.assertTrue(err)
        self.assertEqual(self.m.request("ping")["result"], {})          # 服务器仍然存活


class McpPlatformDownTests(unittest.TestCase):
    def test_tool_call_when_platform_is_down(self):
        m = McpClient("http://127.0.0.1:9")
        try:
            err, text = m.call("system_status")
            self.assertTrue(err)
            self.assertIn("无法连接", text)
        finally:
            m.close()


if __name__ == "__main__":
    unittest.main()
