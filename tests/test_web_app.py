# -*- coding: utf-8 -*-
"""
web_app / compress_tool 的回归测试。运行:
    python -m unittest discover -s tests -v

所有测试都使用临时目录 (DL_DOWNLOADS_DIR / DL_DATA_DIR)，不会碰真实的 downloads。
"""
import os
import sys
import tempfile
import textwrap
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_TMP = tempfile.TemporaryDirectory()
os.environ["DL_DOWNLOADS_DIR"] = os.path.join(_TMP.name, "downloads")
os.environ["DL_DATA_DIR"] = os.path.join(_TMP.name, "data")

import web_app  # noqa: E402
import compress_tool  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(web_app.app)  # 不进入 lifespan → 不启动 worker，任务停留在 pending


def make_drama(plat="Slitz短剧", name="demo"):
    d = os.path.join(web_app.DOWNLOADS_DIR, plat, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "第01集.mp4"), "wb") as f:
        f.write(b"x" * 2048)
    return d


class ParseTargetTests(unittest.TestCase):
    def test_latest_goes_to_reelshort_not_slitz(self):
        # 回归：旧版 "--latest 2" 含 '-' 且不含 '/'，被误判成 Slitz
        r = web_app.parse_target("--latest 2")
        self.assertEqual(r["platform"], "ReelShort")
        self.assertEqual(r["args"], ["--latest", "2"])

    def test_latest_bounds(self):
        with self.assertRaises(ValueError):
            web_app.parse_target("--latest 99")

    def test_platform_urls(self):
        self.assertEqual(web_app.parse_target("https://www.reelshort.com/movie/abc")["platform"], "ReelShort")
        self.assertEqual(web_app.parse_target("https://www.slitz.com/shorts/room-service")["platform"], "Slitz")
        self.assertEqual(web_app.parse_target("room-service")["platform"], "Slitz")
        self.assertEqual(web_app.parse_target("6ab8a43a2cdfd334da0580eb")["platform"], "ReelShort")

    def test_rejects_argument_injection_and_unknown(self):
        for bad in ["", "   ", "--max-eps 3", "-x", "https://evil.example.com/a", "a b", "https://www.slitz.com/a b",
                    "../../etc/passwd", "x" * 3000]:
            with self.assertRaises(ValueError, msg=bad):
                web_app.parse_target(bad)

    def test_lookalike_host_not_accepted(self):
        with self.assertRaises(ValueError):
            web_app.parse_target("https://reelshort.com.evil.io/movie/abc")


class PathSafetyTests(unittest.TestCase):
    def setUp(self):
        self.drama = make_drama()

    def test_valid_path(self):
        self.assertEqual(os.path.normcase(web_app.resolve_drama_dir("Slitz短剧/demo")), os.path.normcase(os.path.realpath(self.drama)))

    def test_traversal_rejected_via_api(self):
        outside = os.path.join(_TMP.name, "outside")
        os.makedirs(outside, exist_ok=True)
        for evil in ["../..", "../outside", "Slitz短剧/../../outside", "..\\..\\", "C:\\Windows", "/etc",
                     os.path.abspath(outside), "Slitz短剧", "", "Slitz短剧/_backup", "Slitz短剧/demo/.."]:
            for ep in ("/api/compress", "/api/zip"):
                r = client.post(ep, json={"path": evil})
                self.assertIn(r.status_code, (400, 404, 422), f"{ep} {evil!r} -> {r.status_code}")

    def test_missing_dir_404(self):
        self.assertEqual(client.post("/api/zip", json={"path": "Slitz短剧/nope"}).status_code, 404)

    def test_no_path_field_422(self):
        self.assertEqual(client.post("/api/compress", json={}).status_code, 422)


class TaskApiTests(unittest.TestCase):
    def test_invalid_url_400(self):
        r = client.post("/api/tasks", json={"url": "https://evil.example.com/x"})
        self.assertEqual(r.status_code, 400)
        r = client.post("/api/tasks", json={"url": "--max-eps 3"})
        self.assertEqual(r.status_code, 400)

    def test_max_eps_validation(self):
        r = client.post("/api/tasks", json={"url": "room-service-a", "max_eps": 0})
        self.assertEqual(r.status_code, 422)

    def test_duplicate_active_task_reused(self):
        a = client.post("/api/tasks", json={"url": "dup-test-slug"}).json()
        b = client.post("/api/tasks", json={"url": "dup-test-slug"}).json()
        self.assertFalse(a["duplicate"])
        self.assertTrue(b["duplicate"])
        self.assertEqual(a["task_id"], b["task_id"])
        client.post(f"/api/tasks/{a['task_id']}/cancel")

    def test_cancel_retry_delete_flow(self):
        tid = client.post("/api/tasks", json={"url": "flow-test-slug"}).json()["task_id"]
        self.assertEqual(client.delete(f"/api/tasks/{tid}").status_code, 409)  # 未结束不可删
        self.assertEqual(client.post(f"/api/tasks/{tid}/cancel").status_code, 200)
        self.assertEqual(client.get(f"/api/tasks/{tid}").json()["data"]["status"], "cancelled")
        self.assertEqual(client.post(f"/api/tasks/{tid}/cancel").status_code, 409)  # 已结束不可再取消
        retry = client.post(f"/api/tasks/{tid}/retry").json()
        self.assertNotEqual(retry["task_id"], tid)
        client.post(f"/api/tasks/{retry['task_id']}/cancel")
        self.assertEqual(client.delete(f"/api/tasks/{tid}").status_code, 200)
        self.assertEqual(client.get(f"/api/tasks/{tid}").status_code, 404)

    def test_list_has_no_full_logs(self):
        tid = client.post("/api/tasks", json={"url": "list-test-slug"}).json()["task_id"]
        web_app.task_manager.append_log(tid, "hello")
        item = next(t for t in client.get("/api/tasks").json()["data"] if t["id"] == tid)
        self.assertNotIn("logs", item)
        self.assertEqual(item["last_log"], "hello")
        self.assertEqual(client.get(f"/api/tasks/{tid}").json()["data"]["logs"], ["hello"])
        client.post(f"/api/tasks/{tid}/cancel")

    def test_dramas_listing_encodes_urls_and_skips_underscore_dirs(self):
        make_drama("Reelshort", "Number One, Nobody #1")
        make_drama("Reelshort", "_repair_backup_x")
        web_app.task_manager.dramas_dirty = True
        data = client.get("/api/dramas").json()["data"]
        names = [d["folder_name"] for d in data]
        self.assertIn("Number One, Nobody #1", names)
        self.assertNotIn("_repair_backup_x", names)
        d = next(x for x in data if x["folder_name"] == "Number One, Nobody #1")
        self.assertIn("%23", d["first_episode_url"])  # '#' 必须被转义，否则浏览器会截断 URL


class PosterValidationTests(unittest.TestCase):
    def test_html_masquerading_as_poster_is_ignored(self):
        # 回归：ReelShort 图片 CDN 返回反爬挑战页(HTML)，旧版直接存成 poster.jpg，前端显示成破图
        d = make_drama("Reelshort", "fake-poster")
        with open(os.path.join(d, "poster.jpg"), "wb") as f:
            f.write(b"<script>function a(a){}</script>")
        web_app.task_manager.dramas_dirty = True
        item = next(x for x in client.get("/api/dramas").json()["data"] if x["folder_name"] == "fake-poster")
        self.assertIsNone(item["poster_url"])
        with open(os.path.join(d, "poster.jpg"), "wb") as f:
            f.write(bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"0" * 64)  # JPEG 文件头
        web_app.task_manager.dramas_dirty = True
        item = next(x for x in client.get("/api/dramas").json()["data"] if x["folder_name"] == "fake-poster")
        self.assertIsNotNone(item["poster_url"])


class AiChatTests(unittest.TestCase):
    def test_url_containing_list_is_a_download_not_a_query(self):
        # 回归：旧版先判断关键词，链接里带 'list' 会被当成“查询”
        r = client.post("/api/ai/chat", json={"message": "下载 https://www.slitz.com/shorts/playlist-demo"}).json()
        self.assertIn("task_id", r)
        client.post(f"/api/tasks/{r['task_id']}/cancel")

    def test_unsupported_url_gives_friendly_reply(self):
        r = client.post("/api/ai/chat", json={"message": "下载 https://evil.example.com/a"}).json()
        self.assertNotIn("task_id", r)
        self.assertIn("处理不了", r["reply"])

    def test_stats_query(self):
        r = client.post("/api/ai/chat", json={"message": "查询已下载的剧"}).json()
        self.assertIn("资产统计", r["reply"])


class WorkerPipelineTests(unittest.TestCase):
    """用桩脚本替代真实下载器，验证 子进程输出 → 进度/目录解析 → 状态流转 的完整链路。"""

    @classmethod
    def setUpClass(cls):
        web_app.task_manager.start_workers()

    def _stub(self, body: str) -> str:
        path = os.path.join(_TMP.name, f"stub_{time.time_ns()}.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(body))
        return path

    def _wait(self, tid, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            t = web_app.task_manager.get_task(tid)
            if t["status"] in web_app.TERMINAL:
                return t
            time.sleep(0.2)
        self.fail(f"任务超时: {web_app.task_manager.get_task(tid)}")

    def _run_with_script(self, script_body, url="stub-slug-a"):
        original = web_app.PLATFORMS["Slitz"]["script"]
        web_app.PLATFORMS["Slitz"]["script"] = self._stub(script_body)
        try:
            tid = client.post("/api/tasks", json={"url": url, "auto_compress": False}).json()["task_id"]
            return self._wait(tid)
        finally:
            web_app.PLATFORMS["Slitz"]["script"] = original

    def test_success_parses_progress_and_dir(self):
        d = make_drama("Slitz短剧", "stub-ok")
        t = self._run_with_script(f"""
            import sys
            sys.stdout.reconfigure(encoding="utf-8")
            print("保存路径: {d.replace(chr(92), '/')}")
            print("[进度] 1/2"); print("[进度] 2/2")
        """, "stub-slug-ok")
        self.assertEqual(t["status"], "completed", t)
        self.assertEqual(t["progress"], 100)
        self.assertEqual(os.path.normcase(t["result_dirs"][0]), os.path.normcase(d))
        logs = web_app.task_manager.get_logs(t["id"])
        self.assertTrue(any("[进度] 2/2" in l for l in logs))

    def test_nonzero_exit_marks_failed(self):
        t = self._run_with_script("import sys; sys.stdout.reconfigure(encoding='utf-8'); print('❌ 未找到视频源'); sys.exit(2)", "stub-slug-fail")
        self.assertEqual(t["status"], "failed")
        self.assertIn("未找到视频源", t["error"])  # 直接展示脚本给出的失败原因
        self.assertIn("重试", t["error"])

    def test_cancel_running_kills_process(self):
        original = web_app.PLATFORMS["Slitz"]["script"]
        web_app.PLATFORMS["Slitz"]["script"] = self._stub("import time; print('started', flush=True); time.sleep(60)")
        try:
            tid = client.post("/api/tasks", json={"url": "stub-slug-cancel", "auto_compress": False}).json()["task_id"]
            end = time.time() + 15
            while time.time() < end and web_app.task_manager.get_task(tid)["status"] != "running":
                time.sleep(0.1)
            time.sleep(1)
            self.assertEqual(client.post(f"/api/tasks/{tid}/cancel").status_code, 200)
            t = self._wait(tid, 15)
            self.assertEqual(t["status"], "cancelled")
        finally:
            web_app.PLATFORMS["Slitz"]["script"] = original

    def test_task_records_persisted(self):
        self.assertTrue(os.path.isfile(web_app.TASKS_FILE))


class CompressToolTests(unittest.TestCase):
    def test_parse_probe_output(self):
        text = ("  Duration: 00:01:53.25, start: 0.000000, bitrate: 1500 kb/s\n"
                "  Stream #0:0[0x1](und): Video: hevc (Main) (hvc1 / 0x31637668), yuv420p, 720x1280, 24 fps\n")
        info = compress_tool.parse_probe_output(text)
        self.assertEqual(info["codec"], "hevc")
        self.assertAlmostEqual(info["duration"], 113.25)
        self.assertIsNone(compress_tool.parse_probe_output("garbage"))

    def test_collect_videos_skips_backups_and_temp(self):
        root = os.path.join(_TMP.name, "collect")
        for rel in ["a/第01集.mp4", "a/第01集.mp4.temp.mp4", "a/x.compressed.mp4", "a/_backup/b.mp4", "a/.hidden/c.mp4", "a/第02集.MP4"]:
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").close()
        got = sorted(os.path.basename(p) for p in compress_tool.collect_videos(os.path.join(root, "a")))
        self.assertEqual(got, sorted(["第01集.mp4", "第02集.MP4"]))

    def test_zip_is_atomic_and_skips_temp_files(self):
        d = make_drama("Slitz短剧", "zipme")
        with open(os.path.join(d, "第01集.mp4.temp.mp4"), "wb") as f:
            f.write(b"junk")
        self.assertTrue(compress_tool.zip_archive(d))
        out = d + ".zip"
        self.assertTrue(os.path.isfile(out))
        self.assertFalse(os.path.exists(out + ".tmp"))
        import zipfile
        names = zipfile.ZipFile(out).namelist()
        self.assertTrue(any(n.endswith("第01集.mp4") for n in names))
        self.assertFalse(any(n.endswith(".temp.mp4") for n in names))


if __name__ == "__main__":
    unittest.main()
