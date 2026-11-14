# ADR-002: Trợ lý tri thức dùng streaming có trích dẫn ở cuối

## Status

Accepted

## Context

Trợ lý tri thức đọc 3 đến 8 đoạn tài liệu rồi trả lời. Prompt trung vị khoảng 370 token, câu trả lời trung vị khoảng 240 token, p95 của tổng thời gian khoảng 17,8 giây và 26% yêu cầu vượt 10 giây. Người hỏi cần đọc kết luận sớm, còn danh sách trích dẫn chỉ cần khi câu trả lời xong.

## Options

- sync: chờ đủ khoảng 17,8 giây ở p95 mới thấy chữ, dễ bị bỏ ngang.
- streaming: chữ đầu tiên đến sau khoảng 0,9 giây; trích dẫn gửi như sự kiện cuối của luồng.
- job: đẩy ra nền; chỉ hợp lý nếu người hỏi không đứng chờ, mà ở đây họ đang chờ.

## Decision

streaming. Kết luận chạy ra trước, sự kiện cuối chứa danh sách mã đoạn trích dẫn đã kiểm.

## Consequences

- Phải kiểm trích dẫn sau khi luồng kết thúc, nên giao diện cần hiển thị trạng thái đang kiểm.
- Cần giới hạn số yêu cầu streaming đồng thời cho mỗi chi nhánh để không giữ quá nhiều kết nối.
