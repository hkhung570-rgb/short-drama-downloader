# AI Agent 接入指南

第一次接手这套平台时，先阅读 [接手手册.md](接手手册.md)，再按本文件配置命令行、MCP 或 REST 接入。

本项目是一个短剧下载 / 压缩 / 资产管理平台。运营人员用网页操作；AI Agent 有三种等价的接入方式，**都是同一个后台、同一套数据**，所以人和 Agent 可以同时使用。

## 沟通语言约定

与越南同事沟通时，默认使用**中文和越南语双语回复**：先给出中文内容，再给出对应的越南语内容。命令、URL、`task_id`、文件路径和错误代码保持原样，便于复制执行。涉及下载、压缩、打包、恢复、删除或其他平台操作时，双语说明结果、任务状态和下一步建议；`purge` 等不可恢复操作必须先取得用户明确同意。

### Quy ước ngôn ngữ giao tiếp

Khi trao đổi với đồng nghiệp Việt Nam, mặc định phải trả lời **song ngữ Trung–Việt**: viết nội dung tiếng Trung trước, sau đó viết nội dung tiếng Việt tương ứng. Giữ nguyên lệnh, URL, `task_id`, đường dẫn tệp và mã lỗi để có thể sao chép. Với các thao tác tải xuống, nén, đóng gói, khôi phục, xóa hoặc thao tác khác trên nền tảng, phải thông báo song ngữ về kết quả, trạng thái tác vụ và bước tiếp theo; các thao tác không thể khôi phục như `purge` phải được người dùng xác nhận rõ ràng trước.

前提：平台已启动（`启动下载平台.bat` 或 `python web_app.py`），默认地址 `http://127.0.0.1:8000`。

| 方式 | 适合 | 入口 |
| :--- | :--- | :--- |
| 命令行 (JSON 输出) | 有 shell 的 Agent (Claude Code 等) | `python dl_cli.py <命令>` |
| MCP 服务器 | Claude Desktop / 支持 MCP 的 Agent | `python mcp_server.py` (见下文配置) |
| REST API | 任意语言 / Dify / 飞书钉钉机器人 | `http://127.0.0.1:8000/docs` (交互式文档)、`/openapi.json` |

环境变量：`DL_URL`（平台地址）、`DL_TOKEN`（平台设置了访问口令时）、`DL_OPERATOR`（在“操作记录”里显示的名字，建议设为 Agent 名）。

## 典型流程

```bash
python dl_cli.py status                                    # 1. 确认平台在线
python dl_cli.py add https://www.slitz.com/shorts/room-service --zip   # 2. 创建下载 → 返回 task_id
python dl_cli.py wait <task_id> --timeout 1800             # 3. 等待完成 (退出码 0=成功, 3=失败/超时)
python dl_cli.py dramas --search room                      # 4. 在资产库确认
```

失败时：`python dl_cli.py task <id> --logs 50` 看原因，网络类错误直接 `retry <id>`（下载会断点续传，已下载的集数自动跳过）。

## 安全约定（Agent 必读）

| 操作 | 是否可逆 | 说明 |
| :--- | :--- | :--- |
| `add / cancel / retry / zip` | 可逆 | 取消后已下载内容保留 |
| `compress` | **可撤销** | 默认原片进回收站，`restore <entry_id>` 换回；`--no-keep-original` 则不可撤销，别轻易用 |
| `delete` | **可恢复** | 只是移入回收站（默认保留 7 天），`restore` 恢复 |
| `purge` | **不可恢复** | 永久删除。必须 `--yes`（API 为 `confirm=true`）。**务必先征得用户明确同意** |

- 删除、永久清理这类操作，先向用户确认再执行。
- `path` 参数一律形如 `平台目录/剧集目录`（先用 `dramas` 查到再用，如 `Slitz短剧/room-service`），不接受别的路径。
- 同一链接已有进行中任务时不会重复创建，返回 `duplicate: true`，复用原 `task_id`。
- 所有改变数据的操作都会写入平台的“操作记录”（含 `DL_OPERATOR`）。

## MCP 配置

Claude Desktop 的 `claude_desktop_config.json`，或项目根目录 `.mcp.json`：

```json
{
  "mcpServers": {
    "short-drama": {
      "command": "python",
      "args": ["C:/Projects/下载工具/mcp_server.py"],
      "env": { "DL_URL": "http://127.0.0.1:8000", "DL_OPERATOR": "claude" }
    }
  }
}
```

提供的工具：`system_status` `add_downloads` `list_tasks` `get_task` `wait_task` `cancel_task` `retry_task` `list_dramas` `compress_drama` `zip_drama` `delete_drama` `list_trash` `restore_trash` `purge_trash`。

## REST 速查

带口令时加请求头 `Authorization: Bearer <DL_TOKEN>`。

| 方法 | 路径 | 说明 |
| :--- | :--- | :--- |
| GET | `/api/health` | 健康检查（无需口令），含 `auth_required` |
| GET | `/api/system` | 编码器、磁盘、并发、回收站保留天数 |
| POST | `/api/tasks/batch` | `{"urls":[...],"auto_compress":true,"auto_zip":false,"keep_original":false}` |
| GET | `/api/tasks` · `/api/tasks/{id}?tail=30` | 任务列表 / 详情+日志 |
| POST | `/api/tasks/{id}/cancel` · `/retry` | 取消 / 重试 |
| GET | `/api/dramas` | 资产库 |
| POST | `/api/compress` | `{"path":"平台/剧","keep_original":true}` |
| POST | `/api/zip` | `{"path":"平台/剧"}` |
| POST | `/api/dramas/delete` | `{"path":"平台/剧"}` → 进回收站 |
| GET | `/api/trash` | 回收站 |
| POST | `/api/trash/{id}/restore` | 恢复 / 撤销压缩 |
| POST | `/api/trash/purge` | `{"ids":[...]|"all":true,"confirm":true}` 不可恢复 |
| GET | `/api/audit` | 操作记录 |

错误统一为 HTTP 状态码 + `{"detail": "中文原因"}`：400 参数/链接不合法，401 需要口令，404 不存在，409 冲突(任务进行中/目录已存在)。

## 在 Python 里直接用

```python
from dl_client import Client
c = Client()
r = c.add(["https://www.slitz.com/shorts/room-service"])
done = c.wait(r["results"][0]["task_id"], timeout=1800)
```
