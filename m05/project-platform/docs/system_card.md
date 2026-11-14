# System card: dịch vụ AI Giao Hàng Anh Tí

## Mục đích và người dùng

Cổng AI dùng chung cho 5 chi nhánh: trò chuyện hỗ trợ khách, trợ lý tri thức và báo cáo tuần. Người dùng là nhân viên chi nhánh (JWT) và ứng dụng đặt đơn của chi nhánh (khóa API).

## Mô hình và nhà cung cấp

Hai provider cùng giao thức OpenAI: chính và phụ. Trong bản tham khảo cả hai là provider giả của khóa học; khi triển khai thật, đặt `PROVIDER_PRIMARY_URL` và `PROVIDER_SECONDARY_URL`, thay bảng giá `prices.json` bằng giá chính thức kèm ngày tra.

## Prompt và phát hành

Hai phiên bản prompt: `v1` ổn định, `v2` canary. Mỗi phiên bản qua cổng đánh giá trên 90 câu trước khi triển khai và qua canary 10 phần trăm với rollback tự động.

## Dữ liệu và quyền riêng tư

Nhật ký không chứa nội dung tin nhắn, chỉ độ dài; số điện thoại và email bị che nếu lọt vào thông báo lỗi. `usage_events` giữ tenant, người dùng, token, chi phí. Không lưu nội dung yêu cầu.

## Giới hạn đã biết

- Điểm chất lượng của bản tham khảo là số mô phỏng; thay bằng giám khảo thật trước khi dùng cho quyết định.
- Giới hạn tốc độ trong bộ nhớ chỉ đúng với một tiến trình; Compose dùng Redis để chia sẻ giữa nhiều tiến trình.
- Chưa có xử lý job nền (Worker) và chưa stream phản hồi.

## Chi phí và hạn mức

Mỗi chi nhánh có ngân sách tháng. Từ 80 phần trăm hạ về model nhỏ; từ 100 phần trăm từ chối. Số liệu chi phí theo bảng giá minh họa.

## Người chịu trách nhiệm và thay đổi

Chủ dịch vụ: nhóm nền tảng AI. Mọi thay đổi prompt, model, hạn mức ghi vào bảng thay đổi dưới đây kèm kết quả cổng đánh giá.

| Ngày | Thay đổi | Cổng đánh giá | Người duyệt |
|---|---|---|---|
| 2026-11-14 | Phát hành v1 | deploy | nhóm nền tảng |
