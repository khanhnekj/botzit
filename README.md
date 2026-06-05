# FBBot Dashboard — Render.com

Bot Facebook Messenger + Web Dashboard quản lý.

## Cấu trúc project

```
render-bot/
├── app.py              # Entry point (bot + web server)
├── requirements.txt    # Dependencies Python
├── config.json         # Cấu hình (KHÔNG push lên GitHub)
├── .gitignore
├── web/
│   └── index.html      # Dashboard giao diện web
└── src/
    ├── _core/          # Session, login Facebook
    ├── _features/      # Các tính năng Facebook
    ├── _messaging/     # Gửi/nhận tin nhắn
    └── modules/        # Các lệnh bot (ping, help, ff...)
```

## Deploy lên Render.com

### 1. Push lên GitHub
```bash
git init
git add .
git commit -m "init bot"
git remote add origin https://github.com/username/ten-repo.git
git push -u origin main
```
> ⚠️ `config.json` đã được .gitignore — cookie sẽ KHÔNG bị push lên.

### 2. Tạo Web Service trên Render
- Vào https://render.com → **New** → **Web Service**
- Kết nối GitHub repo vừa tạo
- Cấu hình:
  - **Runtime:** Python 3
  - **Build Command:** `pip install -r requirements.txt`
  - **Start Command:** `python app.py`
  - **Instance Type:** Free

### 3. Nhập cookie qua Dashboard
- Sau khi deploy xong, mở URL Render của bạn
- Vào tab **⚙️ Cấu Hình**
- Dán cookie Facebook vào ô **Cookie Facebook**
- Nhấn **💾 Lưu Cấu Hình**
- Quay về **🏠 Trang Chủ** → nhấn **▶ Khởi Động Bot**

## Lưu ý quan trọng

- **Render Free:** Service sẽ sleep sau 15 phút không có request
  → Dùng https://uptimerobot.com ping URL mỗi 10 phút để giữ bot online
- **Cookie bảo mật:** Không bao giờ commit `config.json` lên GitHub
- **Node.js không cần** — project này chạy thuần Python 3.10+

## Lệnh bot hỗ trợ

| Lệnh | Mô tả |
|------|-------|
| `/ping` | Kiểm tra độ trễ |
| `/help` | Danh sách lệnh |
| `/id` | Xem threadID + userID |
| `/echo <text>` | Lặp lại nội dung |
| `/search <từ>` | Tìm user Facebook |
| `/unsend` | Thu hồi tin nhắn cuối |
| `/pin <từ khoá>` | Tìm ảnh Pinterest |
| `/love` | Gửi reaction ❤️ |
| `/ff <uid> [region]` | Tra thông tin Free Fire |
| `/lq` | QR chuyển khoản ngân hàng |
