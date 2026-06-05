"""
Module: /kb — Gửi lời mời kết bạn Facebook
Cách dùng:
  /kb <uid>
  /kb <link profile>  (vd: https://fb.com/username hoặc https://www.facebook.com/username)
"""
import re
import requests
from _core._utils import Headers, parse_cookie_string


def _extract_uid_from_link(dataFB: dict, link: str) -> str | None:
    """Lấy UID từ link profile Facebook."""
    # Nếu là số -> đã là UID rồi
    if link.isdigit():
        return link

    # Lấy username từ link
    match = re.search(r'facebook\.com/(?:profile\.php\?id=(\d+)|([^/?&#]+))', link)
    if not match:
        return None

    # Nếu link dạng profile.php?id=123456
    if match.group(1):
        return match.group(1)

    username = match.group(2)
    if username in ("home", "me", "story.php", "messages", "groups"):
        return None

    # Gọi API Graph để lấy UID từ username
    try:
        r = requests.get(
            f"https://www.facebook.com/{username}",
            headers={
                **Headers(),
                "cookie": dataFB["cookieFacebook"],
                "accept": "text/html",
            },
            cookies=parse_cookie_string(dataFB["cookieFacebook"]),
            timeout=15,
        )
        uid_match = re.search(r'"userID":"(\d+)"', r.text) or \
                    re.search(r'"actorID":"(\d+)"', r.text) or \
                    re.search(r'entity_id=(\d+)', r.text)
        if uid_match:
            return uid_match.group(1)
    except Exception:
        pass
    return None


def _send_friend_request(dataFB: dict, uid: str) -> dict:
    """Gửi lời mời kết bạn tới UID."""
    data = (
        f"__a=1"
        f"&fb_dtsg={dataFB.get('fb_dtsg', '')}"
        f"&jazoest={dataFB.get('jazoest', '')}"
        f"&to_friend={uid}"
        f"&action=add_friend"
        f"&how_found=profile_button"
        f"&ref=profile"
        f"&outgoing_id="
        f"&logging_location=profile"
        f"&ccu=1"
        f"&r2r=1"
    )
    headers = {
        **Headers(dataForm=data),
        "cookie": dataFB["cookieFacebook"],
        "content-type": "application/x-www-form-urlencoded",
        "x-fb-friendly-name": "FriendingCometFriendRequestMutation",
        "referer": f"https://www.facebook.com/profile.php?id={uid}",
    }
    r = requests.post(
        "https://www.facebook.com/ajax/add_friend/action.php",
        data=data,
        headers=headers,
        cookies=parse_cookie_string(dataFB["cookieFacebook"]),
        timeout=15,
    )
    return {"status": r.status_code, "text": r.text[:200]}


def handle(bot, snap: dict, arg: str) -> None:
    if not arg:
        bot._reply(snap, (
            f"👥 Cách dùng:\n"
            f"  {bot.prefix}kb <uid>\n"
            f"  {bot.prefix}kb <link profile>\n\n"
            f"Ví dụ:\n"
            f"  {bot.prefix}kb 100012345678\n"
            f"  {bot.prefix}kb https://fb.com/username"
        ))
        return

    arg = arg.strip()
    bot._reply(snap, f"⏳ Đang xử lý...")

    # Lấy UID
    uid = _extract_uid_from_link(bot.dataFB, arg)
    if not uid:
        bot._reply(snap, "❌ Không tìm được UID từ link này. Thử dùng UID số trực tiếp.")
        return

    # Không tự kết bạn với chính mình
    if uid == str(bot.dataFB.get("FacebookID")):
        bot._reply(snap, "❌ Không thể tự kết bạn với chính mình.")
        return

    try:
        result = _send_friend_request(bot.dataFB, uid)
        status = result["status"]
        text   = result["text"]

        if status == 200 and ("error" not in text.lower() or "1" in text):
            bot._reply(snap, f"✅ Đã gửi lời mời kết bạn tới UID: {uid}")
        elif "already_friends" in text or "ALREADY_FRIENDS" in text:
            bot._reply(snap, f"ℹ️ Bạn đã là bạn bè với UID: {uid}")
        elif "sent" in text.lower() or "pending" in text.lower():
            bot._reply(snap, f"⏳ Lời mời đã được gửi trước đó tới UID: {uid}")
        else:
            bot._reply(snap, f"⚠️ Gửi không chắc thành công (HTTP {status}). Kiểm tra lại cookie.")
    except Exception as e:
        bot._reply(snap, f"❌ Lỗi: {e}")
