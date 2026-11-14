# Báo cáo load test

Môi trường: Docker Compose m05c15 trên một máy, provider giả với time scale 0,05 (mọi thời gian model nhanh 20 lần),
một tiến trình API, Redis cho giới hạn tốc độ. Số đo là của lớp nền tảng, không phải của model thật.

| Pha | Tải | Gửi | 200 | 429 | 5xx | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|---|
| Trong hạn mức | 4 rps trong 30 giây | 120 | 120 | 0 | 0 | 344 ms | 372 ms | 382 ms |
| Quá tải | 30 rps trong 20 giây | 600 | 360 | 240 | 0 | 431 ms | 472 ms | 492 ms |

Chi phí lớp nền tảng ở p50: 12 ms so với gọi thẳng provider.
Kết luận: trong hạn mức, không lỗi 5xx; khi quá tải, mỗi chi nhánh bị chặn đúng ở hạn mức của mình bằng 429 trả về trong vài chục mili giây.
