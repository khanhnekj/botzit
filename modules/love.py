"""
Module: love
Bói tình duyên dựa trên tên 2 người.
Cách dùng: /love <tên1> <tên2>
Ví dụ:    /love An Binh
"""

import random


def _boi_tinh_duyen(ten1: str, ten2: str) -> str:
    ten1 = ten1.lower()
    ten2 = ten2.lower()
    common = sum(1 for ch in "abcdefghijklmnopqrstuvwxyz" if ch in ten1 and ch in ten2)

    if common == 0:
        pool = [
            "Người dưng nước lã. 😐",
            "Tình duyên ấm áp chỉ là mơ ước. 💨",
        ]
    elif common == 1:
        pool = [
            "Có duyên nhưng chưa đủ phận. 👀",
            "Chỉ đủ để nảy mùi thân tình thôi. 😏",
        ]
    elif common == 2:
        pool = [
            "Đang yêu nhau lén lút. 🫦",
            "Mối tình bí mật đầy kịch tính. 🔥",
        ]
    else:
        pool = [
            "Tình duyên trọn vẹn như mộng mơ. 💑",
            "Định mệnh đã sắp đặt, tình yêu mãi bên nhau. 💞",
        ]
    return random.choice(pool)


def handle(bot, snap: dict, arg: str) -> None:
    """
    /love <tên1> <tên2>
    Tên có thể có dấu cách nếu dùng _ thay thế, ví dụ: /love Nguyen_Van_A Tran_Thi_B
    """
    parts = arg.strip().split()

    if len(parts) < 2:
        bot._reply(snap, (
            f"💘 Cú pháp: {bot.prefix}love <tên1> <tên2>\n"
            f"  Ví dụ: {bot.prefix}love An Binh\n"
            f"  Tên nhiều từ: {bot.prefix}love Nguyen_Van_A Tran_Thi_B"
        ))
        return

    name1 = parts[0].replace("_", " ")
    name2 = parts[1].replace("_", " ")

    ket_qua = _boi_tinh_duyen(name1, name2)
    result = (
        f"💘 {name1} ❤️ {name2}\n"
        f"━━━━━━━━━━━━\n"
        f"{ket_qua}"
    )
    bot._reply(snap, result)
