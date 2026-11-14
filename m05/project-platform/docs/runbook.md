# Runbook: dịch vụ AI Giao Hàng Anh Tí

Tài liệu cho người trực. Mỗi cảnh báo trong `deploy/alerts.yml` trỏ về một mục dưới đây. Lệnh chạy trên VM, trong thư mục chứa `compose.yaml`.

## Error budget fast burn

Ý nghĩa: tỉ lệ yêu cầu lỗi vượt 14,4 lần mức cho phép của SLO 99 phần trăm trong 5 phút và 1 giờ. Ngân sách 30 ngày cạn sau khoảng 2 ngày nếu để nguyên.

1. Mở bảng `anhti_requests_total` theo `status`. Nếu phần lớn là `server_error`, `timeout` hoặc `AllProvidersFailed`, sang mục Primary provider down.
2. Nếu phần lớn là `RateLimited` hoặc `QuotaExceeded` của một chi nhánh, đó không phải sự cố hệ thống: báo trưởng chi nhánh, không tăng hạn mức khi chưa có ý kiến của chủ ngân sách.
3. Nếu vừa phát hành bản mới trong 30 phút, rollback: `CANARY_PERCENT=0 docker compose up -d api`.
4. Ghi giờ bắt đầu, giờ hết, tác động vào nhật ký sự cố.

## Latency high

Ý nghĩa: p95 độ trễ cổng AI trên 2,5 giây trong 5 phút.

1. So `anhti_request_seconds` với số lần thử lại: `attempts` lớn hơn 1 trong `usage_events` nghĩa là provider chính đang chậm và cổng đang thử lại.
2. Kiểm tra số yêu cầu đồng thời ở provider (`GET /admin/stats` của provider giả, hoặc bảng điều khiển của nhà cung cấp thật).
3. Giảm tải tạm thời: hạ `max_tier` của chi nhánh dùng nhiều nhất hoặc bật tầng `small` cho tính năng chat.

## Primary provider down

Ý nghĩa: provider chính lỗi liên tục; bộ ngắt mạch mở và cổng chuyển sang provider phụ.

1. Xác nhận: `anhti_fallback_total` tăng, `usage_events.fallback_used` bằng true.
2. Kiểm tra trang trạng thái của nhà cung cấp và khóa API (hết hạn, hết hạn mức).
3. Trong lúc chờ, theo dõi chi phí: provider phụ có thể đắt hơn; xem `anhti_cost_usd_total` theo `tenant`.
4. Khi provider chính hồi phục, bộ ngắt mạch tự thử lại sau 30 giây; không cần khởi động lại.

## Canary rollback

Ý nghĩa: điểm chất lượng online của prompt canary (`prompt_version="v2"`) dưới 0,8 trong 10 phút, hoặc bộ điều khiển đã tự rollback.

1. Xác nhận: `GET /metrics` có `anhti_quality_score{prompt_version="v2"}`; đọc 10 câu trả lời mẫu của v2 trong kho đánh giá.
2. Rollback thủ công nếu bộ điều khiển chưa làm: `CANARY_PERCENT=0 docker compose up -d api`.
3. Không phát hành lại v2 trước khi cổng đánh giá trong CI chạy lại và qua.

## Quota exceeded của một chi nhánh

1. `GET /v1/usage` bằng tài khoản quản lý của chi nhánh để xem chi phí theo tính năng.
2. Mức 80 phần trăm: hệ thống tự hạ về tầng `small`. Mức 100 phần trăm: từ chối với mã 402.
3. Tăng hạn mức chỉ khi chủ ngân sách đồng ý bằng văn bản; ghi vào `docs/system_card.md`.

## Xoay khóa bí mật

1. Tạo `JWT_SECRET` mới, cập nhật `.env`, `docker compose up -d api`. Mọi token cũ hết hiệu lực; người dùng đăng nhập lại.
2. Khóa API của tích hợp: phát khóa mới cho chi nhánh, đổi `api_key` trong kho người dùng, thu hồi khóa cũ.
