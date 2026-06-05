"""
Module: ff
Lấy thông tin tài khoản Free Fire từ UID.
Cách dùng: /ff <uid> [region]
Region hỗ trợ: SG (mặc định), IND, BR, US, SAC, ME, TH, ID, TW, VN
Ví dụ:    /ff 12345678
          /ff 12345678 IND
"""

import requests
from datetime import datetime

# Danh sách API thử lần lượt
_APIS = [
    "https://accinfo.vercel.app/player-info?region={region}&uid={uid}",
    "https://ff-info.vercel.app/player-info?region={region}&uid={uid}",
    "https://ffapi.vercel.app/player-info?region={region}&uid={uid}",
]

_REGIONS = {"SG", "IND", "BR", "US", "SAC", "ME", "TH", "ID", "TW", "VN"}
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _fetch_player(uid: str, region: str) -> dict | None:
    """Thử từng API, trả về dict data nếu thành công, None nếu tất cả thất bại."""
    for template in _APIS:
        url = template.format(uid=uid, region=region)
        try:
            r = requests.get(url, timeout=10, headers=_HEADERS)
            if r.status_code == 200:
                data = r.json()
                if data.get("basicInfo"):
                    return data
        except Exception:
            continue
    return None


def handle(bot, snap: dict, arg: str) -> None:
    parts = arg.strip().split()

    if not parts:
        bot._reply(snap, (
            f"❌ Thiếu UID!\n\n"
            f"📌 Cách dùng: {bot.prefix}ff <uid> [region]\n"
            f"  Ví dụ: {bot.prefix}ff 12345678\n"
            f"  Region: SG (mặc định), IND, BR, US, SAC, ME, TH, ID, TW, VN"
        ))
        return

    uid = parts[0]
    region = parts[1].upper() if len(parts) > 1 else "SG"

    if region not in _REGIONS:
        bot._reply(snap, f"❌ Region không hợp lệ!\nHỗ trợ: {', '.join(sorted(_REGIONS))}")
        return

    if not uid.isdigit():
        bot._reply(snap, "❌ UID phải là dãy số. Ví dụ: /ff 3205816917")
        return

    bot._reply(snap, f"⏳ Đang tra UID {uid} trên server {region}...")

    data = _fetch_player(uid, region)

    if not data:
        bot._reply(snap, (
            f"❌ Không tìm thấy UID {uid} (region: {region})\n"
            f"Kiểm tra lại UID và region. Thử: {bot.prefix}ff {uid} IND"
        ))
        return

    basic     = data["basicInfo"]
    clan      = data.get("clanBasicInfo") or {}
    pet       = data.get("petInfo") or {}
    social    = data.get("socialInfo") or {}

    nickname   = basic.get("nickname", "Không rõ")
    level      = basic.get("level", 0)
    rank       = basic.get("rank", 0)
    cs_rank    = basic.get("csRank", 0)
    liked      = basic.get("liked", 0)
    clan_name  = clan.get("clanName", "Không có")
    pet_name   = pet.get("name", "Không có")
    pet_lv     = pet.get("level", 0)
    signature  = social.get("signature") or "Chưa có"
    try:
        created_at = datetime.fromtimestamp(int(basic.get("createAt", 0))).strftime("%d/%m/%Y")
    except Exception:
        created_at = "Không rõ"

    bot._reply(snap, "\n".join([
        "📦 [Thông Tin Free Fire]",
        "━━━━━━━━━━━━━━━━━━━",
        f"👤 Nickname   : {nickname}",
        f"🆔 UID        : {uid} ({region})",
        f"📈 Cấp độ     : {level}",
        f"🏆 Rank BR    : {rank}  |  CS: {cs_rank}",
        f"❤️  Lượt thích : {liked:,}",
        f"👑 Clan       : {clan_name}",
        f"🐾 Pet        : {pet_name} (Lv.{pet_lv})",
        f"📅 Ngày tạo   : {created_at}",
        f"📝 Tiểu sử    : {signature}",
        "━━━━━━━━━━━━━━━━━━━",
    ]))
