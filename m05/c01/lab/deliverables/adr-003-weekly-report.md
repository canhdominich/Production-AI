# ADR-003: Báo cáo tuần chạy bằng job nền

## Status

Accepted

## Context

Agent lập báo cáo tuần gọi mô hình large 4 bước, tổng khoảng 1.400 token đầu ra. Thời gian trung vị khoảng 56 giây, p95 khoảng 109 giây và 39% yêu cầu vượt timeout 60 giây của proxy. Quản lý chi nhánh không đứng chờ: họ mở báo cáo vào sáng thứ Hai.

## Options

- sync: 39% yêu cầu bị proxy cắt, trong khi nhà cung cấp vẫn sinh và tính tiền toàn bộ.
- streaming: giữ kết nối mở hơn 100 giây, vẫn bị cắt khi mạng chập chờn và không ai đọc luồng.
- job: trả về ngay mã công việc, Worker chạy từng bước và ghi kết quả vào PostgreSQL.

## Decision

job. API trả mã job trong vài mili giây; Worker lấy job từ Redis, gọi Gateway và lưu báo cáo; người dùng hỏi trạng thái.

## Consequences

- Cần khóa idempotency theo chi nhánh và tuần để bấm hai lần không tạo hai báo cáo.
- Worker chết giữa chừng thì chạy lại từ đầu và tốn thêm token, nên cần lưu tiến độ từng bước.
- Cần giao diện hiển thị trạng thái và thông báo khi xong.
