# GMIP – Global Macro Intelligence Platform

Nền tảng thu thập dữ liệu vĩ mô toàn cầu (FRED, yfinance), chấm điểm và tạo báo cáo tự động.
- **Backend**: FastAPI + SQLite + APScheduler (06:00 Ingestion, 06:30 Report, múi giờ Asia/Ho_Chi_Minh)
- **Frontend**: Next.js
- Tài liệu: `docs/` (PRD, SRS, TECH_ARCHITECTURE, PLAN)

## Chạy bằng Docker Compose
```bash
cp .env.example .env      # điền FRED_API_KEY, ADMIN_SECRET_KEY
docker compose up -d --build
```
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs · Health: http://localhost:8000/api/v1/system/health
- Dữ liệu SQLite nằm trong volume `gmip_data` (`/app/data/gmip.db`); container `restart: always`.
- `NEXT_PUBLIC_API_URL` được nhúng lúc build và phải truy cập được từ trình duyệt người dùng
  (vd `http://localhost:8000/api/v1` hoặc domain public). Đổi giá trị thì chạy lại `docker compose up -d --build`.

Lệnh hữu ích: `docker compose ps`, `docker compose logs -f backend`, `docker compose down` (giữ dữ liệu; thêm `-v` để xóa).

## Chạy local (dev)
```bash
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
uvicorn app.main:app --reload
# terminal khác
cd frontend && cp .env.example .env.local && npm ci && npm run dev
```

> Không commit `.env`, API key, `venv/`, `node_modules/`, file `*.db`.
