"""
Module: pin
Tìm và gửi ảnh Pinterest theo từ khoá.
Flow: tìm URL → tải về máy → upload lên Facebook → gửi ảnh.
Cách dùng: /pin [từ khoá] [số lượng (mặc định 3, tối đa 6)]
"""

import os
import time
import random
import threading
import urllib.parse

import requests

from _messaging._attachments import func as upload_attachment

# Lịch sử ảnh đã gửi theo (thread_id, keyword) để tránh trùng lặp
_sent_history: dict[str, set] = {}

# Thư mục lưu ảnh tạm
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache_pin")


def _ensure_cache_dir() -> str:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return _CACHE_DIR


def _search_pinterest(keyword: str) -> list[str]:
    """Gọi API Pinterest, trả về danh sách URL ảnh (đã lọc trùng)."""
    encoded = urllib.parse.quote(keyword)
    url = f"https://subhatde.id.vn/pinterest?search={encoded}"
    res = requests.get(url, timeout=20)
    res.raise_for_status()
    data = res.json()
    return list(set(data.get("data") or []))


def _pick_fresh(urls: list[str], history_key: str, count: int) -> list[str]:
    """Chọn ảnh chưa gửi trước đó; reset lịch sử nếu không đủ ảnh mới."""
    if history_key not in _sent_history:
        _sent_history[history_key] = set()
    fresh = [u for u in urls if u not in _sent_history[history_key]]
    if len(fresh) < count:
        _sent_history[history_key].clear()
        fresh = urls
    selected = random.sample(fresh, min(len(fresh), count))
    _sent_history[history_key].update(selected)
    return selected


def _download_image(img_url: str, index: int) -> str | None:
    """Tải ảnh về file tạm, trả về đường dẫn file."""
    try:
        resp = requests.get(img_url, timeout=15)
        resp.raise_for_status()
        path = os.path.join(
            _ensure_cache_dir(),
            f"pin_{int(time.time())}_{index}.jpg"
        )
        with open(path, "wb") as f:
            f.write(resp.content)
        return path
    except Exception:
        return None


def _send_image(bot, snap: dict, filepath: str, caption: str) -> None:
    """Upload ảnh lên Facebook rồi gửi vào thread."""
    thread_id = snap["replyToID"]
    type_chat = "user" if snap.get("type") == "user" else None

    attachment = upload_attachment(filepath, bot.dataFB)
    if not attachment or not attachment.get("attachmentID"):
        return

    attach_id = attachment["attachmentID"]
    attach_type_raw = attachment.get("attachmentType", "image/jpeg")
    # Xác định loại attachment cho _send.py (image / video / file)
    if "video" in attach_type_raw:
        kind = "video"
    elif "gif" in attach_type_raw:
        kind = "gif"
    else:
        kind = "image"

    bot.sender.send(
        bot.dataFB,
        caption,
        thread_id,
        typeAttachment=kind,
        attachmentID=attach_id,
        typeChat=type_chat,
        replyMessage=True,
        messageID=snap.get("messageID"),
    )


def _process(bot, snap: dict, keyword: str, count: int) -> None:
    """Chạy trong daemon thread: tìm ảnh → tải → upload → gửi từng ảnh."""
    # Tìm kiếm ảnh
    try:
        urls = _search_pinterest(keyword)
    except Exception as exc:
        bot._reply(snap, f"❌ Lỗi khi tìm ảnh Pinterest: {exc}")
        return

    if not urls:
        bot._reply(snap, f"🔍 Không tìm thấy ảnh nào cho: \"{keyword}\"")
        return

    history_key = f"{snap.get('replyToID')}_{keyword.lower()}"
    selected = _pick_fresh(urls, history_key, count)

    success = 0
    for i, img_url in enumerate(selected):
        path = _download_image(img_url, i)
        if not path:
            continue
        try:
            caption = f"📸 {keyword} ({i + 1}/{len(selected)})" if i == 0 else ""
            _send_image(bot, snap, path, caption)
            success += 1
        except Exception as exc:
            print(f"[pin] Lỗi gửi ảnh {i}: {exc}")
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    if success == 0:
        bot._reply(snap, "❌ Không thể tải hoặc gửi ảnh nào cả, thử lại sau nhé!")


def handle(bot, snap: dict, arg: str) -> None:
    """Entry point được gọi từ main.py."""
    parts = arg.strip().split()

    if not parts:
        p = bot.prefix
        bot._reply(snap, (
            f"📸 Cách dùng: {p}pin [từ khoá] [số lượng]\n"
            f"  Ví dụ: {p}pin anime girl 3\n"
            f"  Số lượng mặc định: 3, tối đa: 6"
        ))
        return

    # Tách số lượng ở cuối nếu có
    count = 3
    if parts[-1].isdigit():
        count = min(int(parts[-1]), 6)
        keyword = " ".join(parts[:-1])
    else:
        keyword = " ".join(parts)

    if not keyword:
        bot._reply(snap, f"⚠️ Nhập từ khoá nhé! Ví dụ: {bot.prefix}pin anime girl")
        return

    bot._reply(snap, f"⏳ Đang tìm {count} ảnh cho \"{keyword}\"...")

    threading.Thread(
        target=_process,
        args=(bot, snap, keyword, count),
        daemon=True,
    ).start()
