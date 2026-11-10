# 短剧批量下载、智能压缩与全员协同管理平台 (Short Drama Downloader & Web/AI Platform)

本项目是一套面向多平台的短剧（竖屏微短剧、AI 短剧、网络短剧）**自动化逆向解析、多线程切片下载、无损转封装、标准化资产归档、智能视频压缩与 Web/AI 交互管理**的完整工程化体系。

已实现 **“Web 可视化交互 + 命令行脚本 + AI 自然语言对话”** 三位一体协同，让普通同事零门槛在浏览器中操作，同时支持技术人员或 AI Agent 通过对话与 API 批量调度。

## 文档导航

| 文档 | 给谁看 | 内容 |
| :--- | :--- | :--- |
| [使用说明.md](使用说明.md) | 管理员 + 运营 | **完整指南**：安装启动、设置、按场景的操作步骤（含撤销）、AI 使用、故障排查、备份 |
| [Hướng dẫn sử dụng tiếng Việt.md](Hướng dẫn sử dụng tiếng Việt.md) | Đồng nghiệp Việt Nam | Hướng dẫn ngắn bằng tiếng Việt, ưu tiên dùng ChatGPT để quản lý nền tảng |
| [接手手册.md](接手手册.md) | 新电脑 + 新 AI | 代码、数据、配置迁移，以及另一台电脑/另一位 AI 的接手步骤 |
| [使用手册.md](使用手册.md) | 运营/所有同事 | 一页纸上手：启动、批量下载、撤销、回收站、常见问题 |
| [架构图.md](架构图.md) | 维护者/开发者/AI | Web、CLI、MCP、REST、下载器、任务队列和资产库关系 |
| [AGENTS.md](AGENTS.md) | AI Agent / 开发者 | 让 AI 调用本平台：命令行(JSON)、MCP 服务器、REST，含安全约定 |
| 本 README | 维护者/开发者 | 完整功能、API、命令行、目录规范、扩展开发 |
| [进展文档.md](进展文档.md) | 项目负责人 | 当前状态、资产统计、近期改动、验证情况、已知问题 |
| [待办事项.md](待办事项.md) | 维护者 | 按优先级排列的后续工作 |
| [方案.md](方案.md) | 维护者 | 早期调研与合规风险结论（黄果短剧站点），启用相关功能前请先阅读 |

## 越南同事沟通约定

越南同事后续可直接用中文或越南语与 ChatGPT 沟通。默认采用**中越双语**回复：先说明中文结果，再给出对应的越南语内容；命令、URL、`task_id`、路径和错误代码保持原样，方便直接复制执行。每次涉及下载、压缩、打包、恢复或删除时，ChatGPT 应返回任务状态和下一步建议；永久删除（`purge`）等不可恢复操作必须先取得明确同意。详细的越南语操作流程见 [Hướng dẫn sử dụng tiếng Việt.md](Hướng dẫn sử dụng tiếng Việt.md)。

### Quy ước giao tiếp với đồng nghiệp Việt Nam

Đồng nghiệp Việt Nam có thể trao đổi với ChatGPT bằng tiếng Trung hoặc tiếng Việt. Mặc định ChatGPT trả lời **song ngữ Trung–Việt**: nêu kết quả bằng tiếng Trung trước, sau đó cung cấp nội dung tiếng Việt tương ứng. Lệnh, URL, `task_id`, đường dẫn và mã lỗi phải được giữ nguyên để có thể sao chép. Với mọi thao tác tải xuống, nén, đóng gói, khôi phục hoặc xóa, ChatGPT phải báo trạng thái tác vụ và bước tiếp theo; các thao tác không thể khôi phục như `purge` phải được xác nhận rõ ràng trước khi thực hiện. Xem quy trình chi tiết tại [Hướng dẫn sử dụng tiếng Việt.md](Hướng dẫn sử dụng tiếng Việt.md)。

## 当前状态（2026-11-10，v2.2.0）

- **运营友好**：一次粘贴多个链接批量下载；**删除和压缩都可撤销**（回收站，默认保留 7 天）；操作记录（谁在何时做了什么）；可选访问口令；导出资产清单 CSV；失败原因直接展示、一键重试续传。
- **人和 AI 都能用**：同一个后台，网页、命令行（JSON 输出）、MCP 服务器、REST API 四种入口，见 [AGENTS.md](AGENTS.md)。
- **已稳定**：任务队列（取消/重试/去重/重启恢复）、路径与参数安全校验、压缩安全替换、ReelShort 与 Slitz 下载器（原子写入、断点续传、失败退出码）。共 65 项自动化测试，另做过浏览器界面实测与真实网络冒烟，见[第七节](#七-测试)。
- **未纳入加固**：黄果短剧相关脚本（`download_huangguo_video.py`、`compress_huangguo_dramas.py`、`download_interactive.py` 等）保持原状。
- **资产库**：35 部 / 319 集 / 6.62 GB（ReelShort 2、Slitz 23、黄果 10）。
- **架构说明**：网页、CLI、MCP 和 REST 共用同一个 FastAPI 后台，完整关系见 [架构图.md](架构图.md)。
- **站点提示**：站点适配器已经接入，但具体剧目是否可下载取决于页面是否提供当前可用的播放地址；`huangguo.me` 的页面结构变化可能触发 `videoInitialData` 解析错误。

---

## 目录 (Table of Contents)
- [架构图](架构图.md)
- [一、 平台概览与快速启动 (Web & AI)](#一-平台概览与快速启动-web--ai)
  - [1. 快速启动 Web 服务](#1-快速启动-web-服务)
  - [2. 面向全体同事的四大功能模块](#2-面向全体同事的四大功能模块)
  - [3. 面向 AI 用户的对话式与 API 接入](#3-面向-ai-用户的对话式与-api-接入)
- [二、 常用站点下载实战 (底层脚本)](#二-常用站点下载实战-底层脚本)
  - [1. ReelShort (海外头部竖屏短剧)](#1-reelshort-海外头部竖屏短剧)
  - [2. Slitz (海外精品微短剧)](#2-slitz-海外精品微短剧)
  - [3. 黄果短剧 (AI短剧与互动剧)](#3-黄果短剧-ai短剧与互动剧)
- [三、 文件夹归整与标准化规范](#三-文件夹归整与标准化规范)
  - [1. 目录分层架构](#1-目录分层架构)
  - [2. 文件命名规范](#2-文件命名规范)
  - [3. 必备配套资产规范](#3-必备配套资产规范)
- [四、 智能视频压缩与打包归档工具](#四-智能视频压缩与打包归档工具)
  - [1. 压缩能力与技术特性](#1-压缩能力与技术特性)
  - [2. 常用压缩命令](#2-常用压缩命令)
  - [3. 一键打包归档 (ZIP)](#3-一键打包归档-zip)
- [五、 如何新增站点下载 (扩展开发指南)](#五-如何新增站点下载-扩展开发指南)
  - [1. 站点逆向与抓包五步法](#1-站点逆向与抓包五步法)
  - [2. 新增站点代码模板](#2-新增站点代码模板)
- [六、 常见问题与排错 (FAQ)](#六-常见问题与排错-faq)
- [七、 测试](#七-测试)

---

## 一、 平台概览与快速启动 (Web & AI)

为了让**所有同事（无论懂不懂代码）都能方便使用**，项目内置了基于 FastAPI + TailwindCSS + Vue 3 的轻量级 Web 服务 [`web_app.py`](web_app.py)，无需安装复杂环境，单机启动即可在局域网内共享。

### 1. 快速启动 Web 服务
```bash
# 1. 安装核心依赖
pip install -r requirements.txt

# 2. 一键启动 Web 协同平台 (默认端口 8000)；Windows 也可直接双击 启动下载平台.bat
python web_app.py --port 8000

# 仅本机使用 (不对局域网开放)
python web_app.py --host 127.0.0.1
```

> ⚠️ 默认监听 `0.0.0.0`，局域网内任何人都能访问并操作本平台。**多人共用/不完全可信的网络请设置访问口令**：`set DL_TOKEN=你的口令`（建议纯英文数字）后再启动，网页会要求输入，API/Agent 用 `Authorization: Bearer <口令>`。API 默认**不开放跨域**，如需第三方网页调用请设置 `DL_CORS_ORIGINS`。

可选环境变量：`DL_TOKEN`（访问口令）、`DL_WORKERS`（同时执行的任务数，默认 2；压缩阶段始终串行）、`DL_TRASH_DAYS`（回收站保留天数，默认 7）、`DL_DOWNLOADS_DIR`、`DL_DATA_DIR`（任务记录/日志/操作记录，默认 `./data`）。
启动后终端将输出访问入口：
- **本机浏览器访问**：`http://127.0.0.1:8000`
- **局域网同事访问**：`http://<您的局域网IP>:8000`（办公室同事无需配置任何环境，手机/电脑浏览器打开即用）

---

### 2. 面向运营同事的功能模块

| 模块 | 说明 | 亮点体验 |
| :--- | :--- | :--- |
| **⚡ 极速下载** | 一次粘贴多个链接（一行一个），自动识别平台并开始下载 | • 无法识别的链接会逐条说明原因，不影响其余<br>• 【⚡ 自动压缩】省 50%~70% 空间；【↩ 保留原片】可撤销；【📦 自动 ZIP】<br>• 磁盘不足时顶部红字提醒 |
| **📋 任务队列** | 实时查看所有下载/转码/打包任务的进度 | • 受控并发（默认同时 2 个，其余排队），同一链接不会重复创建<br>• 动态进度条、失败原因直接展示，支持**取消 / 重试(断点续传) / 删除**<br>• 一键弹窗查看实时日志；服务重启后任务记录与日志仍在，中断的任务可一键重试 |
| **📚 媒体资产库** | 海报墙总览，可搜索/筛选/排序 | • **在线试看**第 1 集校验画质<br>• ⚡压缩（原片留存可撤销）、📦ZIP（内容更新后提示“↻ZIP”过期）、📂打开目录（本机）、🗑删除（进回收站）<br>• 📥 导出清单 CSV |
| **🗑 回收站** | 删除的剧、压缩前的原片都在这里 | • 保留 7 天内**一键恢复/撤销压缩**（字节级还原），超期自动清理<br>• 永久删除需二次确认；下方“操作记录”显示谁在何时做了什么 |
| **🤖 AI 助手** | 内置关键字意图识别，用一句话下指令 | • 下载链接、查进度、查资产库、“撤销刚才的操作”<br>• 外部 AI Agent 的接入见 [AGENTS.md](AGENTS.md) |

---

### 3. 面向 AI 用户的对话式与 API 接入

对于 AI 能力强的同事，或者需要对接**飞书机器人、钉钉机器人、企业微信机器人、Dify 智能体**的工作流，系统提供了标准接口与内置 NLP 理解能力：

#### (1) 内置 AI 助手交互示例
直接在网页界面的【AI 助手】窗口或调用 `/api/ai/chat` 接口发送文字：
- *"帮我下载 https://www.slitz.com/shorts/room-service 并压缩打包"*
  ➔ **AI 自动提取 URL，开启硬件压缩与 ZIP 打包，后台自动调度并在群内回复任务卡片。**
- *"自动下载 ReelShort 最新的 2 部短剧"*
  ➔ **AI 自动调用 `--latest 2` 探测接口，拉取最新上线的两部剧。**
- *"查询目前短剧库里有哪些剧"*
  ➔ **AI 实时统计已归档剧集数、总集数、占用存储空间并汇总反馈。**

#### (2) 标准 RESTful API 列表
交互式文档：启动后访问 `/docs`（Swagger）、`/openapi.json`。带口令时加请求头 `Authorization: Bearer <口令>`。错误统一为 HTTP 状态码 + `{"detail": "中文原因"}`。

| 方法 · 路径 | 说明 |
| :--- | :--- |
| `POST /api/tasks/batch` | **批量**创建下载：`{"urls":[...],"auto_compress":true,"auto_zip":false,"keep_original":false,"max_eps":3}`，逐个返回成功/重复/失败原因 |
| `POST /api/tasks` | 创建单个下载任务（`url` 也可为 `--latest 2`）；同一目标已有进行中任务时返回该任务并带 `"duplicate": true` |
| `GET /api/tasks` · `GET /api/tasks/{id}?tail=300` | 任务摘要(不含日志) / 详情+日志；`undo_available` 表示可撤销该任务的压缩 |
| `POST /api/tasks/{id}/cancel` · `/retry` · `DELETE /api/tasks/{id}` · `POST /api/tasks/clear` | 取消 / 重试(断点续传) / 删除记录 / 清除已结束 |
| `GET /api/dramas` · `GET /api/dramas/export.csv` | 资产库 / 导出清单 (Excel 可直接打开) |
| `POST /api/compress` | `{"path":"平台目录/剧目录","keep_original":true}`；原片默认进回收站可撤销 |
| `POST /api/zip` | `{"path":"平台目录/剧目录"}` |
| `POST /api/dramas/delete` | `{"path":"..."}` **不会真删**，移入回收站 |
| `GET /api/trash` · `POST /api/trash/{id}/restore` | 回收站列表 / 恢复被删除的剧或撤销压缩 |
| `POST /api/trash/purge` | **永久删除**：`{"ids":[...]}` 或 `{"all":true}`，必须带 `"confirm":true` |
| `GET /api/audit?limit=50` | 操作记录（请求头 `X-Operator: <URL编码的姓名>` 会被记录） |
| `POST /api/open` | 在服务器电脑上打开剧目录（仅本机访问时可用） |
| `GET /api/system` · `GET /api/health` | 编码器/磁盘/并发/回收站天数 · 健康检查(无需口令) |
| `POST /api/login` | 设置了 `DL_TOKEN` 时登录 (设置 cookie) |
| `POST /api/ai/chat` | 自然语言指令（下载、查进度、查资产库、“撤销刚才的操作”） |

#### (3) 给 AI Agent 用
同一个平台还提供命令行（所有输出为 JSON）和 MCP 服务器，详见 [AGENTS.md](AGENTS.md)：

```bash
python dl_cli.py add https://www.slitz.com/shorts/room-service --zip
python dl_cli.py wait <task_id> --timeout 1800      # 退出码 0=成功 3=失败/超时
python dl_cli.py delete "Slitz短剧/room-service"     # 进回收站，可 restore
```
MCP：把 `mcp_server.py` 配到 Claude Desktop / `.mcp.json` 即可（纯标准库，无需安装 SDK）。

---

## 二、 常用站点下载实战 (底层脚本)

除了 Web 页面，后台亦完全支持命令行独立执行：

### 1. ReelShort (海外头部竖屏短剧)
- **官网入口**：[https://www.reelshort.com](https://www.reelshort.com)
- **脚本程序**：[`download_reelshort.py`](download_reelshort.py)
- **核心能力**：
  - 逆向破解 ReelShort 专有 `play_info` 流（AES-128-CBC 加密 + 双重 Base64 编码 + zlib Inflate 压缩）。
  - 自动提取最高清晰度（1080P/720P）未加密 HLS 视频流。
  - 自动抓取剧目元数据、英文标签、剧情简介和官方高清封面海报。
  - 支持多线程（8 线程）并发下载 TS 切片并通过内置 FFmpeg 无损转封装为高兼容性 MP4。

#### 使用命令：
```bash
# 1. 自动拉取并下载最新上线的 2 部短剧全集
python download_reelshort.py --latest 2

# 2. 传入短剧详情页 URL 下载全集
python download_reelshort.py https://www.reelshort.com/movie/6ab8a43a2cdfd334da0580eb

# 3. 传入短剧 Book ID 下载全集
python download_reelshort.py 6ab8a43a2cdfd334da0580eb

# 4. 仅下载前 N 集（快速验证或提取样片）
python download_reelshort.py 6ab8a43a2cdfd334da0580eb --max-eps 3
```

---

### 2. Slitz (海外精品微短剧)
- **官网入口**：[https://www.slitz.com](https://www.slitz.com)
- **脚本程序**：[`download_slitz.py`](download_slitz.py)
- **核心能力**：
  - 智能路由探测 BunnyCDN 高速节点（自动匹配 `candy` 频道或 `originals` 原创频道）。
  - 自动探测多清晰度直链（`-hd.mp4` / `.mp4` / `-sd.mp4`）并提取最大体积 HD 高清源。
  - 全自动化生成三件套：官方高清封面（`poster.webp`/`poster.jpg`）、`metadata.json` 结构化元数据、以及自动编写的中文详细剧情与角色解析（`剧集说明.md`）。
  - 自动同步更新总索引清单（`downloads/Slitz短剧/README.md` 与 `dramas_list.md`）。

#### 使用命令：
```bash
# 1. 传入 Slitz 网页链接下载
python download_slitz.py https://www.slitz.com/shorts/room-service

# 2. 传入剧集 Slug 标识符下载
python download_slitz.py room-service

# 3. 批量并发下载多部短剧
python download_slitz.py https://www.slitz.com/shorts/drama-a https://www.slitz.com/shorts/drama-b
```

---

### 3. 黄果短剧 (AI短剧与互动剧)
- **播放入口**：`https://nv5et.wrjmtnebd.cc/`、`https://huangguodrama.ai/`
- **脚本程序**：
  - 单剧全集下载：[`download_huangguo_video.py`](download_huangguo_video.py)
  - 网页版解析：[`prototype/hg.py`](prototype/hg.py) / [`download_drama.py`](download_drama.py)
  - 互动分支剧：[`download_interactive.py`](download_interactive.py)
  - 文档与资产补全：[`prototype/generate_huangguo_docs.py`](prototype/generate_huangguo_docs.py)
- **核心能力**：
  - 使用可配置的非 Windows UA（`DL_HG_UA`），降低站点返回 `444` 的概率，并支持 `Referer`。
  - 自动解析 M3U8 清单中的 `#EXT-X-KEY:METHOD=AES-128`，动态拉取鉴权 Key，基于 Crypto 并发解密切片。
  - 支持 M3U8 master playlist 展开、分片缺失检测、失败重试和 FFmpeg 自动转封装为 MP4。
  - 使用 `.part` 临时文件并在成功后原子改名，避免半成品覆盖正式视频。
  - 支持多分支选择互动剧（生成完整剧情走向树与选项清单），页面请求和视频下载均带重试与 HTTP 校验。

#### 使用命令：
```bash
# 1. 单剧全集多线程下载
python download_huangguo_video.py https://nv5et.wrjmtnebd.cc/video/5860/

# 2. 批量连续下载多部剧
python download_huangguo_video.py https://nv5et.wrjmtnebd.cc/video/8714/ https://nv5et.wrjmtnebd.cc/video/7628/

# 3. 下载互动短剧分支片段
python download_interactive.py

# 4. 指定互动短剧 URL（站点地址变化时无需修改源码）
python download_interactive.py https://huangguodrama.ai/en/interactive/hehuan-sect/
```

> 黄果站点状态（2026-11）：`huangguodrama.ai` 互动页可解析 19 个视频节点；
> `nv5et.wrjmtnebd.cc` 具体剧页可解析剧名、集数和 `videoSrc`。`huangguo.me` 因未解锁时不返回
> `videoUrl`，已从当前支持清单排除，不作为可下载来源。网页可访问不等于已接入下载器。

> Trạng thái Huangguo (2026-11): trang interactive của `huangguodrama.ai` phân tích được 19 node video;
> trang phim của `nv5et.wrjmtnebd.cc` lấy được tên phim, số tập và `videoSrc`. Do `huangguo.me` không trả
> `videoUrl` khi chưa mở khóa, domain này đã bị loại khỏi danh sách hỗ trợ hiện tại.

---

## 三、 文件夹归整与标准化规范

为了便于多平台资源的长期归档、媒体服务器（如 Jellyfin、Emby、Plex）挂载以及批量分发，所有下载产物均严格遵守以下**目录与命名规范**：

### 1. 目录分层架构
```
downloads/
├── <平台名称>/                                    # 第一层：按平台/站点隔离 (如 Reelshort, Slitz短剧, 黄果短剧)
│   ├── README.md                                 # 平台归档总览说明
│   ├── dramas_list.md                            # 平台剧集列表清单与大小统计
│   │
│   └── <剧集目录>/                                # 第二层：剧集独立目录 (采用剧集Slug、英文名或 "ID_中文名")
│       ├── poster.jpg (或 poster.webp)           # 官方高清封面海报
│       ├── metadata.json                         # 结构化原始元数据
│       ├── 剧集说明.md                           # 中文剧情、角色、题材与分集清单
│       ├── 第01集.mp4                            # 标准格式视频 (H.264 / HEVC + AAC)
│       ├── 第02集.mp4
│       ├── ...
│       └── 第NN集(大结局).mp4                     # 最后一集必须显式标注 "(大结局)"
```

### 2. 文件命名规范
1. **集数补零对齐**：
   - 总集数在 100 集以内的，集数补齐为两位数：`第01集.mp4`、`第02集.mp4` ... `第10集.mp4`。
   - 总集数超过 100 集的，集数补齐为三位数：`第001集.mp4` ... `第120集.mp4`。
2. **大结局标识**：
   - 剧目的最后一集文件必须命名为：`第NN集(大结局).mp4`，便于用户一眼识别完结状态。
3. **文件名安全过滤**：
   - 目录名与文件名必须剔除 Windows/Linux 非法字符：`\ / * ? : " < > |`，统一替换为下划线 `_` 或连字符 `-`。

### 3. 必备配套资产规范
每个剧集目录下必须具备以下“三件套”配套资产：
- **`poster.jpg` / `poster.webp`**：官方高清海报封面，通常为 720P/1080P 竖版构图。
- **`metadata.json`**：机器可读的结构化数据，包含：
  ```json
  {
    "slug": "room-service",
    "title": "Room Service",
    "chinese_title": "客房服务 / 致命套房",
    "platform": "Slitz (Vertical Micro-drama)",
    "official_url": "https://www.slitz.com/shorts/room-service",
    "episodes_count": 5,
    "total_size_mb": 95.57,
    "tags": ["都市悬疑", "微短剧"],
    "summary": "剧集详细背景与主线梗概...",
    "poster_file": "poster.webp",
    "episodes": [
      { "filename": "第01集.mp4", "size_mb": 16.79 }
    ]
  }
  ```
- **`剧集说明.md`**：人类可读的 Markdown 文档，包含基本信息表、本地文件目录树、分集大小清单和剧情深度解析。

---

## 四、 智能视频压缩与打包归档工具

微短剧通常采用竖屏拍摄，原片码率可能偏高（5~10 Mbps），全集下载后常占用 1GB~4GB 空间。为此，本项目配备了专用压缩脚本 [`compress_tool.py`](compress_tool.py)。

### 1. 压缩能力与技术特性
- **智能硬件加速**：
  - 自动检测并优先采用 **Intel QuickSync** 硬件加速（`hevc_qsv`、`h264_qsv`），实现高达 5x~10x 的极速硬件编码。
  - 支持 **NVIDIA NVENC** 硬件加速（`hevc_nvenc`、`h264_nvenc`）。
  - 若系统无硬件加速，无缝自动回退到高质量 CPU 多线程软解软编（`libx265` / `libx264`）。
- **高压缩比 (HEVC / H.265)**：
  - 默认采用 HEVC 编码（质量等级 CRF 26），在肉眼画质几乎零损失的情况下，**体积缩减 50% ~ 75%**。
  - 音频自动采用 AAC 128k 重新压制，消除冗余音频流。
  - 封装增加 `-movflags +faststart`，优化网络串流与秒开加载。
- **安全替换机制 (`--replace`)**：
  - 仅在压缩成功、**时长与宽高比和原片一致**、且新文件体积**明确小于原文件**时才进行原子替换；否则保留原片。
  - 替换过程带 `.bak` 备份，失败自动回滚；上次异常中断遗留的 `.bak` / `.temp.mp4` 下次运行时自动还原/清理。
  - 已经是目标编码 (HEVC) 的视频自动跳过，避免重复转码损失画质；确需重压加 `--force`。
  - 硬件编码失败或画面比例异常时，自动回退 CPU 编码重试该集。
  - 自动跳过 `_` 开头的备份目录、`.compressed.mp4` 与临时文件。
  - `--backup-dir DIR`：与 `--replace` 合用，被替换的原片移入该目录而不是删除；Web 平台用它实现“撤销压缩”（原片进 `downloads/_trash/`）。
  - 退出码：`0` 全部成功(含跳过)，`1` 参数/路径错误，`2` 有视频压缩失败。

> **宽高比校验（2026-10-19 起）**：`compress_tool.py` 和 `compress_huangguo_dramas.py` 压缩后都会对比原片的显示宽高比（按 SAR/旋转换算，容差 0.5%）。不一致的结果会被丢弃，原文件保持不动。此前 `hevc_qsv` 路径没有缩放保护，只有《纪念日按摩》受影响，且从未上传或发布。

### 2. 常用压缩命令
```bash
# 1. 预检模式 (仅统计待压缩文件与当前体积，不执行压缩)
python compress_tool.py "downloads/Slitz短剧/room-service" --dry-run

# 2. 压缩整部短剧 (默认另存为 .compressed.mp4，不覆盖原视频)
python compress_tool.py "downloads/Slitz短剧/room-service"

# 3. 压缩整部短剧并安全替换原文件 (推荐，大幅节省磁盘空间)
python compress_tool.py "downloads/Slitz短剧/room-service" --replace

# 4. 指定使用 H.264 编码 (兼容老旧设备/车载屏/播放器)
python compress_tool.py "downloads/Reelshort/Number One, Nobody" --codec h264 --replace

# 5. 微调画质与压缩率 (CRF 23-30，数值越大约小，默认 26)
python compress_tool.py "downloads/黄果短剧/7628_时停手表" --crf 26 --replace

# 6. 对整个平台目录或单个文件进行压缩
python compress_tool.py "downloads/Slitz短剧" --replace
python compress_tool.py "downloads/Slitz短剧/room-service/第01集.mp4" --replace
```

### 3. 一键打包归档 (ZIP)
当需要将整部剧分享给他人或冷备份时，可以使用内置的 `--zip` 指令快速打包：
```bash
# 将指定短剧文件夹打包为紧凑的 .zip 归档文件
python compress_tool.py --zip "downloads/Slitz短剧/room-service"
# 输出: downloads/Slitz短剧/room-service.zip
```

---

## 五、 如何新增站点下载 (扩展开发指南)

当遇到新的短剧站点需要支持时，推荐按照以下标准化流程进行逆向分析与脚本编写：

### 1. 站点逆向与抓包五步法

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 1. 抓包探测数据源 │ ──> │ 2. 破解反爬与鉴权 │ ──> │ 3. 定位流媒体播放源 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐              │
│ 5. 归档三件套资产 │ <── │ 4. 编写下载转封装 │ <────────────┘
└─────────────────┘     └─────────────────┘
```

1. **Step 1：抓包探测数据源**
   - 打开浏览器开发者工具（F12 -> Network），访问剧目详情页与播放页。
   - **优先看 HTML 内嵌数据**：搜索 `<script id="__NEXT_DATA__">`（Next.js 站点如 ReelShort）、`<script>window.__NUXT__</script>` 或内嵌全局 JSON。通常全剧剧集列表、剧名、封面都在这里，无需额外发数百次 API 请求。
   - **其次看 API 请求**：过滤 `fetch` / `xhr`，查找 `chapter/list`、`episode/info`、`playlet/detail` 等接口。
2. **Step 2：破解反爬与鉴权**
   - **User-Agent 规则**：如黄果平台对带有 `Windows` 字样的 UA 直接返回 444，需要将 UA 设为通用 Safari/Mac UA 或纯净 `Mozilla/5.0`。
   - **Referer 检查**：部分 CDN 节点（如 AWS CloudFront、BunnyCDN）严格校验 `Referer`，请求头中需携带站点主域。
   - **Token 有效期**：查看播放 URL 中的签名参数（如 `t=时间戳`、`ticket=`、`auth_key=`），注意签名通常有时效性（如 10 分钟），需采用“即解析即下载”策略。
3. **Step 3：定位流媒体播放源**
   - **情况 A (直链 MP4)**：如 Slitz，CDN 直链带规则后缀（`ep01-hd.mp4`），直接 HEAD 探测最高规格后多线程拉取。
   - **情况 B (普通 HLS M3U8)**：拉取 M3U8 文本，按行读取 TS 分片，并发多线程下载并拼装。
   - **情况 C (加密 HLS AES-128)**：检查 `#EXT-X-KEY:METHOD=AES-128,URI="..."`，拉取 16 字节 Key，使用 `Crypto.Cipher.AES.new(key, AES.MODE_CBC, iv)` 解密每个分片。
   - **情况 D (专有混淆数据流)**：如 ReelShort 的 `play_info`，逆向前端 JS 中的解密逻辑（常见为 Base64 + AES + zlib/gzip）。
4. **Step 4：编写下载转封装器**
   - 多线程下载切片（推荐 6~12 线程并发）。
   - 将 TS 切片或直接 MP4 通过 `imageio_ffmpeg` 执行：
     ```bash
     ffmpeg -y -i input.ts -c copy -bsf:a aac_adtstoasc -movflags +faststart output.mp4
     ```
5. **Step 5：归档三件套资产**
   - 下载封面为 `poster.jpg`。
   - 写入 `metadata.json`。
   - 自动格式化输出 `剧集说明.md`。

---

### 2. 新增站点代码模板
新增站点脚本时，可直接参考以下标准结构编写：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新站点短剧解析与下载器 (模板)
"""
import os, sys, re, json, time, urllib.request, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def http_get(url, referer=None):
    headers = {"User-Agent": UA}
    if referer: headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()

def parse_drama(drama_url):
    """1. 解析剧目详情、海报与剧集列表"""
    html = http_get(drama_url).decode('utf-8', 'ignore')
    # TODO: 提取剧名、封面、全部分集播放链接
    title = "示例剧名"
    cover_url = "https://example.com/cover.jpg"
    episodes = [
        {"ep": 1, "url": "https://example.com/ep1.m3u8"},
        {"ep": 2, "url": "https://example.com/ep2.m3u8"}
    ]
    return {"title": title, "cover_url": cover_url, "episodes": episodes}

def download_drama(drama_meta, out_dir):
    """2. 按项目规范建档下载"""
    safe_title = re.sub(r'[\\/*?:"<>|]', '_', drama_meta["title"]).strip()
    target_dir = os.path.join(out_dir, safe_title)
    os.makedirs(target_dir, exist_ok=True)
    
    # 下载封面
    with open(os.path.join(target_dir, "poster.jpg"), "wb") as f:
        f.write(http_get(drama_meta["cover_url"]))

    # 循环下载视频并转封装
    total = len(drama_meta["episodes"])
    for item in drama_meta["episodes"]:
        ep = item["ep"]
        is_last = (ep == total)
        name = f"第{ep:02d}集(大结局).mp4" if is_last else f"第{ep:02d}集.mp4"
        save_path = os.path.join(target_dir, name)
        # TODO: 下载流并转封装为 MP4
        print(f"正在下载: {name}")

    # 保存元数据与说明
    with open(os.path.join(target_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(drama_meta, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        meta = parse_drama(sys.argv[1])
        download_drama(meta, "downloads/新站点短剧")
```

---

## 六、 常见问题与排错 (FAQ)

### Q1: 运行提示 `ModuleNotFoundError: No module named 'Crypto'`
**解决方案**：安装 `pycryptodome`：
```bash
pip install pycryptodome
```
*注意：不要安装旧版的 `pycrypto`。*

### Q2: 下载到一半网络超时或中断，如何断点续传？
**解决方案**：项目中所有下载器均具备**幂等校验机制**。只需重新运行同一条命令，下载器会自动检测本地已存在的视频文件（文件存在且体积有效），自动跳过已下载集数，仅继续下载缺失或未完成的剧集。

### Q3: 视频下载后体积过大（如一部剧占用 3GB 以上），如何快速批量压缩？
**解决方案**：直接使用本项目提供的智能压缩工具，搭配 Intel QSV 硬件加速，几分钟即可完成整剧无损压缩并节省 50%~75% 空间：
```bash
python compress_tool.py "downloads/Reelshort/Number One, Nobody" --replace
```

### Q3.1: 下载中断后重试，会不会拿到半截文件？
不会。下载器先写 `.part` / `.temp.mp4` 临时文件，校验完整后才原子改名为正式文件名，“文件存在”即代表完整。脚本以退出码 `0` 表示全部成功、`2` 表示有集数失败，Web 平台据此显示“失败”并给出原因，点【重试】即可续传。

### Q3.2: 启动时报 “端口 8000 已被占用”？
说明平台已经在运行，直接访问 `http://127.0.0.1:8000` 即可；或用 `--port 8001` 换端口。

### Q3.3: 资产库里某部剧的海报是占位图？
ReelShort 的图片 CDN 有时会返回反爬挑战页而不是图片，旧版本会把它存成 `poster.jpg`。现在下载器会校验文件头、不再保存非图片，资产库也会忽略已有的坏文件。需要海报时请手动放一张 `poster.jpg` 到剧集目录。

### Q3.4: 误删了剧 / 压缩后画质不满意怎么办？
都可以撤销：打开【回收站】点“恢复”或“撤销压缩”（保留期内，默认 7 天）。手动压缩默认保留原片；自动压缩要勾选【压缩时保留原片】才会保留（会多占空间）。永久删除或超过保留期的无法找回。

### Q4: 遇到某些站点报 403 Forbidden 或 444 错误？
**解决方案**：通常是反爬机制触发：
1. 检查 `User-Agent`，尝试移除其中的 `Windows` 关键词。
2. 确保请求头附带了正确的 `Referer`。
3. 检查流媒体 URL 中的签名 ticket 是否过期，确保解析出地址后立即并发下载。

---

*本项目仅供自动化工程、流媒体协议分析与多媒体处理学术研究使用，请自觉遵守各平台用户协议与本地版权法律法规。*

---

## 七、 测试

```bash
python -m unittest discover -s tests -v          # 65 项，约 45 秒
```
测试使用临时目录，不会触碰真实的 `downloads/`。覆盖：

| 文件 | 内容 |
| :--- | :--- |
| `tests/test_web_app.py` | 站点识别与参数注入防护、路径穿越防护、任务取消/重试/去重、桩脚本验证“子进程输出 → 进度/目录解析 → 状态流转”、海报校验、压缩工具探测/收集/ZIP |
| `tests/test_undo.py` | 回收站（删除→恢复字节级一致、冲突、过期清理）、**真实 ffmpeg 压缩→撤销字节级还原**、批量提交、CSV、访问口令、操作记录、“正在处理的剧不可删除” |
| `tests/test_agent.py` | 对真实平台子进程测 Python 客户端、命令行(JSON 与退出码)、MCP 握手/工具调用/错误路径/平台宕机 |

另做过的人工验证：浏览器里走通登录、批量提交、压缩→撤销、删除→恢复、回收站与操作记录；真实网络下 Slitz 探测+单集下载、ReelShort 元数据→HLS→MP4。
