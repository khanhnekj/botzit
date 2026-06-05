def handle(bot, snap: dict, arg: str) -> None:
    p = bot.prefix
    bot._reply(snap, (
        "📖 Lệnh hỗ trợ:\n"
        f"• {p}ping                      — kiểm tra độ trễ\n"
        f"• {p}help                      — hiển thị trợ giúp\n"
        f"• {p}id                        — xem threadID + userID\n"
        f"• {p}echo <text>               — lặp lại nội dung\n"
        f"• {p}search <từ>               — tìm user Facebook\n"
        f"• {p}unsend                    — thu hồi tin nhắn cuối của bot\n"
        f"• {p}pin <từ khoá> [số lượng] — tìm ảnh Pinterest (mặc định 3)\n"
        f"• {p}qrbank <STK> <mã NH> [tên TK] [số tiền] [nội dung]\n"
        f"           — tạo QR chuyển khoản ngân hàng\n"
        f"           Mã NH: vcb, tcb, mb, acb, bidv, tpbank, vpbank…"
    ))
