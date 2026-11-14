# Production-AI

Mã nguồn lab của khóa "Production AI: Triển khai, giám sát và tối ưu chi phí dịch vụ AI" (chương trình AI Engineering của GDev). Thư mục `m05/c01` đến `m05/c14` là các chương, `m05/project-platform` là dự án cuối khóa (dịch vụ AI nhiều chi nhánh có xác thực, hạn mức chi phí, fallback, CI có cổng đánh giá và giám sát), `m05/data` và `m05/platform` là phần nền dùng chung (5 chi nhánh, bảng giá minh họa, bộ sinh tải, provider giả có chèn lỗi, khung gateway).

Kịch bản là công ty giao hàng giả định Giao Hàng Anh Tí. Mọi dữ liệu và bảng giá là dữ liệu tổng hợp để học cách tính; thay bằng giá và số liệu thật của bạn khi áp dụng (xem `m05/data/DATA_CARD.md`).

## Chạy thử

Cần `uv`, Python 3.12, Docker (PostgreSQL với pgvector cổng 55432, user, mật khẩu và database đều là `anhti`) và Ollama với `qwen3:1.7b` cho các ví dụ gọi model thật. Một số ví dụ dùng Redis (`redis-server` cục bộ) và Docker Compose.

```bash
uv sync
docker run -d --name anhti-pg -p 55432:5432 -e POSTGRES_USER=anhti -e POSTGRES_PASSWORD=anhti -e POSTGRES_DB=anhti pgvector/pgvector:pg17
docker run -d --name anhti-ollama -p 11434:11434 -v ollama:/root/.ollama ollama/ollama && docker exec anhti-ollama ollama pull qwen3:1.7b
```

Mỗi chương có `examples/` và `lab/{starter,solution,tests}`. Dự án: `m05/project-platform/{starter,solution,tests}` (83 test, dùng provider giả, không cần tải model). Phần chạy cần GPU, tài khoản cloud hay tên miền công khai được ghi rõ là chưa chạy trong bài học. Một số ví dụ đọc dữ liệu của các khóa trước (`m02/data`, `m03/data`, `m04/data` trong các repo LLM-Engineering, RAG-Engineering, AI-Agent-Engineering): chép các thư mục đó vào cùng cấu trúc nếu muốn chạy. Thư mục `cache/` không nằm trong repo.
