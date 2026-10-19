# -*- coding: utf-8 -*-
"""撤销/回收站/批量/鉴权/审计/导出等“运营安全网”相关测试。"""
import json
import os
import shutil
import time
import unittest
from datetime import datetime, timedelta

from _env import web_app, live_server, make_video, sha
import trash
from dl_client import Client, DLError
from fastapi.testclient import TestClient

client = TestClient(web_app.app)  # 进程内，无 worker：任务留在 pending，随后被取消


def dl_root():
    return web_app.DOWNLOADS_DIR


def make_drama(plat, name, files=2, with_zip=False):
    d = os.path.join(dl_root(), plat, name)
    os.makedirs(d, exist_ok=True)
    for i in range(1, files + 1):
        with open(os.path.join(d, f"第{i:02d}集.mp4"), "wb") as f:
            f.write(os.urandom(4096) + bytes([i]))
    if with_zip:
        with open(d + ".zip", "wb") as f:
            f.write(b"PK-fake")
    return d


def snapshot(d):
    return {n: sha(os.path.join(d, n)) for n in sorted(os.listdir(d)) if os.path.isfile(os.path.join(d, n))}


class InProcessBase(unittest.TestCase):
    def tearDown(self):
        # 取消本用例创建的所有进行中任务，避免之后 worker 启动时去真的联网下载
        for t in web_app.task_manager.list_tasks():
            if t["status"] in ("pending", "running"):
                web_app.task_manager.cancel(t["id"])


class TrashModuleTests(InProcessBase):
    def test_delete_and_restore_roundtrip_is_byte_identical(self):
        d = make_drama("Slitz短剧", "undo-del", with_zip=True)
        before = snapshot(d)
        eid = trash.move_drama_to_trash(dl_root(), d)
        self.assertFalse(os.path.exists(d))
        self.assertFalse(os.path.exists(d + ".zip"))
        trash.restore(dl_root(), eid)
        self.assertEqual(snapshot(d), before)
        self.assertTrue(os.path.isfile(d + ".zip"))
        self.assertFalse(os.path.exists(os.path.join(dl_root(), "_trash", eid)))

    def test_restore_conflict_when_same_name_exists(self):
        d = make_drama("Slitz短剧", "undo-conflict")
        eid = trash.move_drama_to_trash(dl_root(), d)
        make_drama("Slitz短剧", "undo-conflict")  # 用户又下载了同名剧
        with self.assertRaises(trash.TrashError) as cm:
            trash.restore(dl_root(), eid)
        self.assertEqual(cm.exception.status, 409)
        self.assertTrue(any(e["id"] == eid for e in trash.list_entries(dl_root())))  # 条目还在，没丢
        trash.purge(dl_root(), [eid])

    def test_entry_id_path_traversal_rejected(self):
        for bad in ["..", "../x", "a/b", ".hidden", ""]:
            with self.assertRaises(trash.TrashError):
                trash.restore(dl_root(), bad)

    def test_expired_entries_are_purged_and_fresh_kept(self):
        d1 = make_drama("Slitz短剧", "exp-old")
        d2 = make_drama("Slitz短剧", "exp-new")
        old = trash.move_drama_to_trash(dl_root(), d1)
        new = trash.move_drama_to_trash(dl_root(), d2)
        mpath = os.path.join(dl_root(), "_trash", old, "manifest.json")
        with open(mpath, encoding="utf-8") as f:
            m = json.load(f)
        m["created_at"] = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(m, f)
        self.assertEqual(trash.purge_expired(dl_root(), 7), 1)
        ids = [e["id"] for e in trash.list_entries(dl_root())]
        self.assertNotIn(old, ids)
        self.assertIn(new, ids)
        trash.purge(dl_root(), [new])

    def test_empty_compress_backup_is_discarded(self):
        eid, _ = trash.begin_compress_backup(dl_root(), "Slitz短剧", "x")
        self.assertFalse(trash.finalize_compress_backup(dl_root(), eid))
        self.assertFalse(os.path.exists(os.path.join(dl_root(), "_trash", eid)))


class DeleteApiTests(InProcessBase):
    def test_delete_goes_to_trash_and_restore_via_api(self):
        d = make_drama("Slitz短剧", "api-del", with_zip=True)
        before = snapshot(d)
        r = client.post("/api/dramas/delete", json={"path": "Slitz短剧/api-del"})
        self.assertEqual(r.status_code, 200, r.text)
        eid = r.json()["trash_id"]
        self.assertFalse(os.path.exists(d))
        names = [x["folder_name"] for x in client.get("/api/dramas").json()["data"]]
        self.assertNotIn("api-del", names)
        listed = client.get("/api/trash").json()
        self.assertTrue(any(e["id"] == eid and e["kind"] == "delete" for e in listed["data"]))
        self.assertEqual(client.post(f"/api/trash/{eid}/restore").status_code, 200)
        self.assertEqual(snapshot(d), before)
        self.assertEqual(client.post(f"/api/trash/{eid}/restore").status_code, 404)  # 不能重复恢复

    def test_delete_rejects_traversal_and_missing(self):
        for evil in ["../..", "Slitz短剧/../..", "Slitz短剧", "_trash/x", "C:\\Windows\\System32"]:
            self.assertIn(client.post("/api/dramas/delete", json={"path": evil}).status_code, (400, 404), evil)
        self.assertEqual(client.post("/api/dramas/delete", json={"path": "Slitz短剧/nope-zzz"}).status_code, 404)

    def test_delete_refused_while_busy(self):
        d = make_drama("Slitz短剧", "api-busy")
        lock = web_app.task_manager.dir_lock(d)
        with lock:  # 模拟有任务正在处理这个目录
            r = client.post("/api/dramas/delete", json={"path": "Slitz短剧/api-busy"})
        self.assertEqual(r.status_code, 409)
        self.assertTrue(os.path.isdir(d))

    def test_delete_refused_when_task_active_on_dir(self):
        d = make_drama("Slitz短剧", "api-busy2")
        r = client.post("/api/zip", json={"path": "Slitz短剧/api-busy2"})  # 进程内无 worker → 一直 pending
        self.assertEqual(r.status_code, 200)
        self.assertEqual(client.post("/api/dramas/delete", json={"path": "Slitz短剧/api-busy2"}).status_code, 409)

    def test_purge_requires_confirm_and_target(self):
        d = make_drama("Slitz短剧", "api-purge")
        eid = client.post("/api/dramas/delete", json={"path": "Slitz短剧/api-purge"}).json()["trash_id"]
        self.assertEqual(client.post("/api/trash/purge", json={"ids": [eid]}).status_code, 400)          # 无 confirm
        self.assertEqual(client.post("/api/trash/purge", json={"confirm": True}).status_code, 400)       # 无目标
        self.assertTrue(any(e["id"] == eid for e in client.get("/api/trash").json()["data"]))            # 仍在
        r = client.post("/api/trash/purge", json={"ids": [eid], "confirm": True})
        self.assertEqual(r.json()["removed"], 1)
        self.assertFalse(any(e["id"] == eid for e in client.get("/api/trash").json()["data"]))

    def test_ai_chat_undo_restores_latest(self):
        d = make_drama("Slitz短剧", "ai-undo")
        before = snapshot(d)
        client.post("/api/dramas/delete", json={"path": "Slitz短剧/ai-undo"})
        r = client.post("/api/ai/chat", json={"message": "撤销刚才的操作"}).json()
        self.assertIn("恢复", r["reply"])
        self.assertEqual(snapshot(d), before)


class BatchAndExportTests(InProcessBase):
    def test_batch_mixed_results(self):
        r = client.post("/api/tasks/batch", json={"urls": [
            "batch-slug-one", "https://evil.example.com/x", "", "batch-slug-one", "--max-eps 3"]}).json()
        self.assertEqual(r["summary"], {"created": 1, "duplicate": 1, "failed": 2})
        self.assertEqual([x["ok"] for x in r["results"]], [True, False, True, False])
        self.assertTrue(all("error" in x for x in r["results"] if not x["ok"]))

    def test_batch_limits(self):
        self.assertEqual(client.post("/api/tasks/batch", json={"urls": []}).status_code, 422)
        self.assertEqual(client.post("/api/tasks/batch", json={"urls": ["a-b"] * 51}).status_code, 422)

    def test_csv_export(self):
        make_drama("Slitz短剧", "csv-demo")
        r = client.get("/api/dramas/export.csv")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"\xef\xbb\xbf"))  # BOM：Excel 直接打开不乱码
        text = r.content.decode("utf-8-sig")
        self.assertIn("平台,剧名", text.splitlines()[0])
        self.assertIn("csv-demo", text)

    def test_open_folder_only_from_localhost(self):
        make_drama("Slitz短剧", "open-demo")
        r = client.post("/api/open", json={"path": "Slitz短剧/open-demo"})  # TestClient 的来源不是回环地址
        self.assertEqual(r.status_code, 403)
        self.assertFalse(client.get("/api/system").json()["data"]["local"])

    def test_audit_records_who_did_what(self):
        make_drama("Slitz短剧", "audit-demo")
        client.post("/api/dramas/delete", json={"path": "Slitz短剧/audit-demo"},
                    headers={"X-Operator": "%E5%B0%8F%E7%8E%8B"})  # 小王
        recs = client.get("/api/audit?limit=5").json()["data"]
        hit = next(r for r in recs if r["action"].startswith("删除剧集"))
        self.assertEqual(hit["operator"], "小王")
        self.assertIn("audit-demo", hit["detail"])


class AuthTests(unittest.TestCase):
    def setUp(self):
        os.environ["DL_TOKEN"] = "s3cret-token"

    def tearDown(self):
        os.environ.pop("DL_TOKEN", None)

    def test_api_and_media_require_token_but_health_and_index_do_not(self):
        c = TestClient(web_app.app)
        self.assertEqual(c.get("/api/tasks").status_code, 401)
        self.assertEqual(c.post("/api/compress", json={"path": "a/b"}).status_code, 401)
        self.assertEqual(c.get("/api/dramas/export.csv").status_code, 401)
        self.assertEqual(c.get("/media/anything.mp4").status_code, 401)
        h = c.get("/api/health").json()
        self.assertTrue(h["auth_required"])
        self.assertFalse(h["authed"])
        self.assertEqual(c.get("/").status_code, 200)  # 页面本身要能打开，才能显示登录框

    def test_header_and_cookie_login(self):
        c = TestClient(web_app.app)
        self.assertEqual(c.get("/api/tasks", headers={"Authorization": "Bearer wrong"}).status_code, 401)
        self.assertEqual(c.get("/api/tasks", headers={"Authorization": "Bearer s3cret-token"}).status_code, 200)
        self.assertEqual(c.get("/api/tasks", headers={"X-Token": "s3cret-token"}).status_code, 200)
        self.assertEqual(c.post("/api/login", json={"token": "wrong"}).status_code, 401)
        self.assertEqual(c.post("/api/login", json={"token": "s3cret-token"}).status_code, 200)
        self.assertEqual(c.get("/api/tasks").status_code, 200)       # cookie 生效
        self.assertTrue(c.get("/api/health").json()["authed"])

    def test_no_token_configured_means_open(self):
        os.environ.pop("DL_TOKEN", None)
        self.assertEqual(TestClient(web_app.app).get("/api/tasks").status_code, 200)


class CompressUndoE2ETests(unittest.TestCase):
    """真实子进程服务 + 真实 ffmpeg：压缩→撤销，字节级还原。"""

    @classmethod
    def setUpClass(cls):
        cls.base, cls.dl = live_server()
        cls.c = Client(cls.base, operator="e2e")

    def _drama(self, name, n=2):
        d = os.path.join(self.dl, "Slitz短剧", name)
        make_video(os.path.join(d, "第01集.mp4"), 3)
        for i in range(2, n + 1):
            shutil.copy(os.path.join(d, "第01集.mp4"), os.path.join(d, f"第{i:02d}集.mp4"))
        return d

    def _wait(self, tid, timeout=180):
        t = self.c.wait(tid, timeout=timeout, interval=0.5)
        self.assertEqual(t["status"], "completed", t)
        return t

    def test_compress_then_undo_restores_original_bytes(self):
        d = self._drama("e2e-undo")
        before = snapshot(d)
        size_before = sum(os.path.getsize(os.path.join(d, n)) for n in before)
        r = self.c.compress("Slitz短剧/e2e-undo")                       # 默认 keep_original=True
        t = self._wait(r["task_id"])
        after = snapshot(d)
        self.assertNotEqual(after, before)                              # 确实被压缩替换了
        self.assertLess(sum(os.path.getsize(os.path.join(d, n)) for n in after), size_before)
        self.assertTrue(t["undo_available"])
        entries = [e for e in self.c.trash()["data"] if e["id"] in t["trash_ids"]]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["kind"], "compress")
        self.assertEqual(entries[0]["file_count"], 2)
        self.c.restore(entries[0]["id"])                                # 撤销
        self.assertEqual(snapshot(d), before)                           # 字节完全一致
        self.assertFalse(self.c.task(r["task_id"])["undo_available"])   # 撤销后按钮应消失

    def test_compress_without_keep_original_creates_no_trash_entry(self):
        d = self._drama("e2e-nokeep", n=1)
        n_before = len(self.c.trash()["data"])
        r = self.c.compress("Slitz短剧/e2e-nokeep", keep_original=False)
        t = self._wait(r["task_id"])
        self.assertFalse(t["undo_available"])
        self.assertEqual(len(self.c.trash()["data"]), n_before)

    def test_second_compress_skips_already_hevc_and_leaves_no_empty_trash(self):
        d = self._drama("e2e-twice", n=1)
        self._wait(self.c.compress("Slitz短剧/e2e-twice")["task_id"])
        n = len(self.c.trash()["data"])
        t2 = self._wait(self.c.compress("Slitz短剧/e2e-twice")["task_id"])
        self.assertEqual(t2["trash_ids"], [])                           # 全部跳过 → 空条目被丢弃
        self.assertEqual(len(self.c.trash()["data"]), n)

    def test_delete_then_restore_over_http(self):
        d = self._drama("e2e-delete", n=1)
        before = snapshot(d)
        r = self.c.delete_drama("Slitz短剧/e2e-delete")
        self.assertFalse(os.path.exists(d))
        self.c.restore(r["trash_id"])
        self.assertEqual(snapshot(d), before)


if __name__ == "__main__":
    unittest.main()
