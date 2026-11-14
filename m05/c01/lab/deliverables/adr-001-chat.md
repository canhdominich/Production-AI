# ADR-001: Chat dùng streaming

## Status

Accepted

## Context

Nhân viên chăm sóc khách hàng gõ câu hỏi và chờ trả lời ngay. Với mô hình cỡ medium, câu trả lời trung vị khoảng 2,2 giây và p95 khoảng 7,7 giây, nhưng p99 lên tới 13 giây. Người dùng đọc được từng chữ khi chữ đầu tiên đến sau khoảng 0,4 giây. Proxy cắt kết nối sau 60 giây, nên chat không chạm trần đó.

## Options

- sync: trả cả câu một lần. Đơn giản, nhưng người dùng nhìn màn hình trống tới 7,7 giây ở p95.
- streaming: gửi từng mẩu chữ qua SSE. Chữ đầu tiên đến sau khoảng 0,4 giây; nếu provider ngừng sinh khi luồng đóng (cần đo lại ở provider thật) thì hủy giữa chừng tiết kiệm phần token còn lại.
- job: đưa vào hàng đợi rồi hỏi lại kết quả. Thừa phức tạp cho một cuộc trò chuyện đang diễn ra.

## Decision

streaming. API mở một kết nối SSE tới người dùng và đọc luồng từ Gateway; Gateway ghi usage khi luồng kết thúc.

## Consequences

- Cần cấu hình Caddy không đệm phản hồi và để timeout đủ dài cho luồng.
- Usage chỉ biết đủ sau chunk cuối, nên Gateway phải xử lý trường hợp client ngắt giữa chừng.
- Retry sau khi đã gửi chữ đầu tiên không an toàn; fallback chỉ áp dụng trước chữ đầu tiên.
