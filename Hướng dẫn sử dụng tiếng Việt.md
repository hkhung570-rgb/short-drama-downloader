# Hướng dẫn sử dụng nền tảng tải phim ngắn

> Sơ đồ kiến trúc của nền tảng: [架构图.md](架构图.md). Hướng dẫn đầy đủ bằng tiếng Trung: [使用说明.md](使用说明.md).

Tài liệu này dành cho đồng nghiệp Việt Nam tiếp nhận dự án. Nền tảng dùng chung một dữ liệu cho trình duyệt và ChatGPT/AI Agent.

## 1. Khởi động và truy cập

1. Trên máy chủ, mở thư mục dự án `C:\Projects\下载工具`.
2. Chạy `启动下载平台.bat` hoặc lệnh:

```powershell
python web_app.py --host 0.0.0.0 --port 8000
```

3. Trên máy chủ mở `http://127.0.0.1:8000`. Máy khác trong cùng mạng mở `http://<IP-máy-chủ>:8000`.
4. Không đóng cửa sổ màu đen đang chạy nền. Nếu nền tảng yêu cầu mật khẩu, dùng mật khẩu do quản trị viên cung cấp; không ghi mật khẩu vào Git hoặc tài liệu công khai.

Nếu ChatGPT/AI Agent được kết nối từ máy khác, cấu hình địa chỉ máy chủ, không dùng `127.0.0.1` của máy AI:

```powershell
$env:DL_URL = "http://<IP-máy-chủ>:8000"
$env:DL_TOKEN = "<mật khẩu nếu có>"
$env:DL_OPERATOR = "ChatGPT-Vietnam"
python dl_cli.py status
```

Lệnh `status` phải báo nền tảng đang hoạt động trước khi thực hiện công việc.

## 2. Dùng ChatGPT để quản lý

Hãy nói rõ việc cần làm, kèm liên kết phim nếu có. Ví dụ:

- `Kiểm tra trạng thái nền tảng và các tác vụ đang chạy.`
- `Tải phim từ https://www.slitz.com/shorts/room-service và tự động nén.`
- `Tải các liên kết sau, chờ hoàn tất và báo phim nào thất bại: <danh sách liên kết>`
- `Chỉ tải 3 tập đầu để kiểm tra.`
- `Liệt kê các phim đã tải, số tập và dung lượng.`
- `Nén phim Slitz/room-service và giữ bản gốc để có thể khôi phục.`
- `Đóng gói phim Slitz/room-service thành ZIP.`
- `Xem nội dung thùng rác và khôi phục mục vừa xóa.`

ChatGPT sẽ tạo hoặc theo dõi tác vụ. Có thể đóng trình duyệt; tác vụ vẫn tiếp tục khi máy chủ còn chạy. Khi có lỗi mạng, yêu cầu: `Thử lại tác vụ <task_id>`.

## 3. Quy trình làm việc khuyến nghị

1. Gửi liên kết và yêu cầu tải.
2. Chờ ChatGPT xác nhận `task_id` và trạng thái hoàn tất.
3. Kiểm tra thư viện tài sản (Assets) hoặc yêu cầu ChatGPT liệt kê phim.
4. Nếu cần gửi cho người khác, yêu cầu tạo ZIP rồi tải tệp ZIP.
5. Nếu muốn tiết kiệm dung lượng, yêu cầu nén và giữ bản gốc trong lần đầu.

Các nền tảng hiện được hỗ trợ chủ yếu là ReelShort và Slitz. Chỉ tải nội dung công khai và tuân thủ điều khoản của website cùng pháp luật bản địa.

## 4. Quy tắc an toàn

- `delete` chỉ chuyển phim vào thùng rác; có thể dùng `restore` để khôi phục trong thời gian lưu giữ mặc định 7 ngày.
- Nén mặc định giữ bản gốc để có thể hoàn tác. Không yêu cầu xóa bản gốc nếu chưa được người phụ trách đồng ý.
- `purge` hoặc xóa vĩnh viễn là **không thể khôi phục**. ChatGPT phải hỏi và nhận được sự đồng ý rõ ràng trước khi thực hiện.
- Khi yêu cầu nén, khôi phục hoặc xóa, dùng đúng đường dẫn do thư viện tài sản trả về, dạng `Tên nền tảng/Tên phim`.
- Mỗi người hoặc AI dùng một `DL_OPERATOR` riêng để có thể tra cứu trong nhật ký thao tác.
- Không gửi `DL_TOKEN`, cookie, dữ liệu thư mục `downloads/` hoặc `data/` lên Git hay vào cuộc trò chuyện công khai.

## 5. Khi có sự cố

- Không mở được trang: kiểm tra máy chủ còn chạy và đúng địa chỉ IP/port 8000.
- Tác vụ thất bại do timeout hoặc mất mạng: yêu cầu ChatGPT `retry`; các tập đã tải hợp lệ sẽ được bỏ qua.
- Không thấy phim: kiểm tra thư mục dữ liệu và yêu cầu ChatGPT chạy `status` rồi `dramas`.
- Không chắc phải làm gì: gửi `task_id`, thông báo lỗi và vài dòng log cho quản trị viên; không tự dùng `purge`.

Thông tin bàn giao cần giữ an toàn: địa chỉ máy chủ, vị trí thư mục `downloads/` và `data/`, kho Git, nơi lưu mật khẩu, các tác vụ đang chạy và tên `DL_OPERATOR` của người tiếp nhận.
