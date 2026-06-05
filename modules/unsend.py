from datetime import datetime
from _messaging._unsend import func as unsend_message

def handle(bot, snap: dict, arg: str) -> None:
    # Chỉ admin mới được dùng nếu có cấu hình admins
    sender_id = str(snap.get("userID") or "")
    if bot.admins and sender_id not in bot.admins:
        bot._reply(snap, "⛔ Chỉ admin mới được dùng lệnh này.")
        return

    thread_id = str(snap["replyToID"])
    target = bot._last_bot_message.get(thread_id)
    if not target:
        bot._reply(snap, "ℹ️ Chưa có tin nào để thu hồi trong thread này.")
        return

    result = unsend_message(target, bot.dataFB)
    print(f"[{datetime.now():%H:%M:%S}] [unsend] {target} -> {result}")
    
    # Sau khi thu hồi → quên ID đó
    bot._last_bot_message.pop(thread_id, None)
