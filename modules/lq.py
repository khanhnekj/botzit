"""
Module: lq
Tra cứu Tướng & Trang phục Liên Quân Mobile.
Cách dùng:
  /lq <tên tướng>   — Hiện danh sách skin
  /lq <số>          — Xem chi tiết skin (sau khi đã tìm tướng)
Ví dụ:
  /lq tachi
  /lq 1
"""

import io
import os
import re
import json
import time
import textwrap
import threading
import random

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from _messaging._attachments import func as upload_attachment

# ------------------------------------------------------------------
# Cấu hình
# ------------------------------------------------------------------
_HERE        = os.path.dirname(__file__)
_DATA_DIR    = os.path.join(_HERE, "..", "data")
_CACHE_FILE  = os.path.join(_DATA_DIR, "lq_champs.json")
_BG_FOLDER   = "background"

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

# Session: {thread_id: (timestamp, slug, author_id)}
_sessions: dict[str, tuple] = {}

# ------------------------------------------------------------------
# Tiện ích
# ------------------------------------------------------------------
def _remove_accent(text: str) -> str:
    s = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', text)
    s = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', s)
    s = re.sub(r'[ìíịỉĩ]', 'i', s)
    s = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', s)
    s = re.sub(r'[ùúụủũưừứựửữ]', 'u', s)
    s = re.sub(r'[ỳýỵỷỹ]', 'y', s)
    s = re.sub(r'[đ]', 'd', s)
    return s


def _get_bg(width: int, height: int) -> Image.Image:
    if os.path.isdir(_BG_FOLDER):
        imgs = [os.path.join(_BG_FOLDER, f) for f in os.listdir(_BG_FOLDER)
                if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if imgs:
            try:
                bg = Image.open(random.choice(imgs)).convert("RGBA")
                bg = bg.resize((width, height), Image.Resampling.LANCZOS)
                return bg.filter(ImageFilter.GaussianBlur(radius=20))
            except Exception:
                pass
    return Image.new("RGBA", (width, height), (15, 15, 20, 255))


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = ['tahomabd.ttf' if bold else 'tahoma.ttf',
             'arialbd.ttf' if bold else 'arial.ttf']
    for name in names:
        for base in [os.path.join("font", name), f"C:\\Windows\\Fonts\\{name}", name]:
            if os.path.exists(base):
                try:
                    return ImageFont.truetype(base, size)
                except Exception:
                    pass
    return ImageFont.load_default()


def _ensure_data():
    os.makedirs(_DATA_DIR, exist_ok=True)


def _send_image(bot, snap: dict, filepath: str, caption: str = "") -> None:
    """Upload ảnh lên Facebook rồi gửi."""
    thread_id = snap["replyToID"]
    type_chat = "user" if snap.get("type") == "user" else None
    attachment = upload_attachment(filepath, bot.dataFB)
    if not attachment or not attachment.get("attachmentID"):
        bot._reply(snap, "❌ Upload ảnh thất bại.")
        return
    bot.sender.send(
        bot.dataFB, caption, thread_id,
        typeAttachment="image",
        attachmentID=attachment["attachmentID"],
        typeChat=type_chat,
        replyMessage=True,
        messageID=snap.get("messageID"),
    )


# ------------------------------------------------------------------
# Lấy slug tướng
# ------------------------------------------------------------------
def _fetch_champ_list():
    try:
        html = requests.get(
            "https://lienquan.garena.vn/hoc-vien/tuong-skin/",
            headers=_HEADERS, timeout=15
        ).text
        soup = BeautifulSoup(html, 'html.parser')
        champs = []
        for a in soup.find_all('a', href=True):
            if '/hoc-vien/tuong-skin/d/' in a['href']:
                slug = a['href'].strip('/').split('/')[-1]
                name = a.text.strip()
                if slug and name:
                    champs.append({"name": name, "slug": slug})
        if champs:
            _ensure_data()
            with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(champs, f, ensure_ascii=False)
    except Exception:
        pass


def _get_slug(name: str) -> str:
    name_clean = name.lower().strip()
    target = _remove_accent(name_clean).replace(' ', '-')
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, 'r', encoding='utf-8') as f:
                heroes = json.load(f)
            for h in heroes:
                if (h['slug'] == target
                        or _remove_accent(h['name'].lower()) == target
                        or h['name'].lower() == name_clean):
                    return h['slug']
    except Exception:
        pass
    return target


# ------------------------------------------------------------------
# Vẽ ảnh danh sách skin
# ------------------------------------------------------------------
def _draw_list_image(bot, snap, hero_name: str, skins: list) -> None:
    row_h    = 130
    canvas_w = 800
    canvas_h = 150 + len(skins) * row_h + 100

    bg = _get_bg(canvas_w, canvas_h)
    overlay = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 160))
    bg.alpha_composite(overlay)
    draw = ImageDraw.Draw(bg)

    font_title = _get_font(44, bold=True)
    font_item  = _get_font(28, bold=True)
    font_hint  = _get_font(20)

    draw.text((40, 40), f"👕 SKIN: {hero_name.upper()}", font=font_title, fill=(255, 215, 0, 255))

    y = 150
    for i, s in enumerate(skins, 1):
        if s.get('thumb'):
            try:
                data = requests.get(s['thumb'], headers=_HEADERS, timeout=5).content
                t = Image.open(io.BytesIO(data)).convert('RGBA').resize((100, 100), Image.LANCZOS)
                mask = Image.new('L', (100, 100), 0)
                ImageDraw.Draw(mask).rounded_rectangle((0, 0, 100, 100), radius=15, fill=255)
                t.putalpha(mask)
                bg.paste(t, (40, y), t)
            except Exception:
                pass
        draw.text((160, y + 30), f"{i}. {s['name']}", font=font_item, fill=(255, 255, 255))
        y += row_h

    draw.text((40, canvas_h - 60),
              f"💡 Gõ: {bot.prefix}lq [số STT] để xem chi tiết skin.",
              font=font_hint, fill=(200, 200, 200))

    _ensure_data()
    out = os.path.join(_DATA_DIR, f"lq_list_{int(time.time())}.jpg")
    bg.convert('RGB').save(out, quality=90)
    try:
        _send_image(bot, snap, out, f"👕 Danh sách skin của {hero_name}")
    finally:
        try: os.remove(out)
        except OSError: pass


# ------------------------------------------------------------------
# Vẽ ảnh chi tiết skin + kỹ năng
# ------------------------------------------------------------------
def _draw_skin_image(bot, snap, soup, img_url: str, title: str) -> None:
    skill_icons = [img.get('src') for img in soup.select('.hero__skills--list img') if img.get('src')]
    skills = []
    for i, detail in enumerate(soup.find_all(class_='hero__skills--detail')[:4]):
        h3  = detail.find('h3')
        art = detail.find('article')
        if h3 and art:
            sn = h3.text.strip()
            sd = art.text.strip()
            if sd.startswith(sn):
                sd = sd[len(sn):].strip()
            skills.append({"name": sn, "desc": sd, "icon": skill_icons[i] if i < len(skill_icons) else None})

    try:
        img_data = requests.get(img_url, headers=_HEADERS, timeout=15).content
        base_img = Image.open(io.BytesIO(img_data)).convert('RGBA')
    except Exception as exc:
        bot._reply(snap, f"❌ Không tải được ảnh splash art: {exc}")
        return

    font_title      = _get_font(50, bold=True)
    font_skill_name = _get_font(30, bold=True)
    font_skill_desc = _get_font(24)

    banner_w = 1100
    banner_h = int(base_img.height * (banner_w / base_img.width))
    cur_y    = banner_h + 200
    for sk in skills:
        sk['wrapped'] = textwrap.wrap(sk['desc'], width=75)
        sk['h'] = max(100, 45 + len(sk['wrapped']) * 35) + 40
        cur_y += sk['h']

    canvas_w, canvas_h = 1200, cur_y + 50
    bg = _get_bg(canvas_w, canvas_h)
    overlay = Image.new('RGBA', (canvas_w, canvas_h), (10, 10, 15, 200))
    bg.alpha_composite(overlay)
    draw = ImageDraw.Draw(bg)

    banner = base_img.resize((banner_w, banner_h), Image.LANCZOS)
    mask = Image.new('L', banner.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, banner_w, banner_h), radius=30, fill=255)
    banner.putalpha(mask)
    bg.paste(banner, (50, 50), banner)

    draw.text((50, banner_h + 80), (title or "UNKNOWN").upper(), font=font_title, fill=(255, 215, 0, 255))

    y = banner_h + 200
    for sk in skills:
        if sk.get('icon'):
            try:
                ic = Image.open(io.BytesIO(requests.get(sk['icon'], headers=_HEADERS, timeout=10).content))
                ic = ic.convert('RGBA').resize((80, 80), Image.LANCZOS)
                m = Image.new('L', (80, 80), 0)
                ImageDraw.Draw(m).rounded_rectangle((0, 0, 80, 80), radius=15, fill=255)
                ic.putalpha(m)
                bg.paste(ic, (50, y), ic)
            except Exception:
                pass
        draw.text((150, y), sk['name'], font=font_skill_name, fill=(255, 255, 255))
        dy = y + 45
        for line in sk['wrapped']:
            draw.text((150, dy), line, font=font_skill_desc, fill=(210, 210, 210))
            dy += 35
        y += sk['h']

    _ensure_data()
    out = os.path.join(_DATA_DIR, f"lq_panel_{int(time.time())}.jpg")
    bg.convert('RGB').save(out, quality=90)
    try:
        _send_image(bot, snap, out, f"✨ Chi tiết: {title}")
    finally:
        try: os.remove(out)
        except OSError: pass


# ------------------------------------------------------------------
# Worker threads
# ------------------------------------------------------------------
def _process_init(bot, snap: dict, hero_name: str) -> None:
    if not os.path.exists(_CACHE_FILE):
        _fetch_champ_list()
    slug = _get_slug(hero_name)
    url  = f"https://lienquan.garena.vn/hoc-vien/tuong-skin/d/{slug}/"

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        if resp.status_code != 200:
            bot._reply(snap, f"❌ Không tìm thấy tướng '{hero_name}'.")
            return

        soup = BeautifulSoup(resp.text, 'html.parser')
        skin_links = soup.select('.hero__skins--list a')
        if not skin_links:
            bot._reply(snap, f"❌ Không lấy được danh sách skin của {hero_name}.")
            return

        skins = []
        for a in skin_links:
            img_tag = a.find('img')
            skins.append({"name": a.get('title'), "thumb": img_tag.get('src') if img_tag else None})

        thread_id  = str(snap["replyToID"])
        author_id  = str(snap.get("userID") or "")
        _sessions[thread_id] = (time.time(), slug, author_id)

        _draw_list_image(bot, snap, hero_name, skins)

    except Exception as exc:
        bot._reply(snap, f"❌ Lỗi khởi tạo: {exc}")


def _process_skin(bot, snap: dict, slug: str, index: int) -> None:
    url = f"https://lienquan.garena.vn/hoc-vien/tuong-skin/d/{slug}/"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, 'html.parser')
        skin_details = soup.select('.hero__skins--detail')
        skin_links   = soup.select('.hero__skins--list a')

        if index < 1 or index > len(skin_details):
            bot._reply(snap, f"❌ Số {index} không hợp lệ. Chỉ có 1–{len(skin_details)}.")
            return

        skin_name = skin_links[index - 1].get('title')
        all_imgs  = skin_details[index - 1].find_all('img')

        img_url = None
        for im in all_imgs:
            src = im.get('src', '')
            if src and ('Honeyview' in src or 'wp-content' in src or '/hero/' in src) and '/SkinLabel/' not in src:
                img_url = src
                break
        if not img_url:
            for im in reversed(all_imgs):
                src = im.get('src', '')
                if src and '/SkinLabel/' not in src:
                    img_url = src
                    break
        if not img_url:
            meta = soup.find('meta', property='og:image')
            img_url = meta.get('content') if meta else None

        if not img_url:
            bot._reply(snap, "❌ Không tìm thấy ảnh cho skin này.")
            return

        if img_url.startswith('//'): img_url = 'https:' + img_url
        elif img_url.startswith('/'): img_url = 'https://lienquan.garena.vn' + img_url

        _draw_skin_image(bot, snap, soup, img_url, skin_name)

    except Exception as exc:
        bot._reply(snap, f"❌ Lỗi: {exc}")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
def handle(bot, snap: dict, arg: str) -> None:
    """
    /lq <tên tướng>   — tìm tướng và hiện danh sách skin
    /lq <số>          — xem chi tiết skin (cần tìm tướng trước)
    """
    keyword   = arg.strip()
    thread_id = str(snap["replyToID"])
    author_id = str(snap.get("userID") or "")

    if not keyword:
        bot._reply(snap, (
            f"⚔️ Cách dùng:\n"
            f"  {bot.prefix}lq <tên tướng>  — tìm skin\n"
            f"  {bot.prefix}lq <số>         — xem chi tiết\n"
            f"Ví dụ: {bot.prefix}lq tachi"
        ))
        return

    # Nếu là số → chọn skin từ session
    if keyword.isdigit():
        session = _sessions.get(thread_id)
        if not session:
            bot._reply(snap, f"⚠️ Chưa có session. Tìm tướng trước: {bot.prefix}lq tachi")
            return
        stime, slug, orig_author = session
        if time.time() - stime > 600:
            del _sessions[thread_id]
            bot._reply(snap, "⚠️ Session đã hết hạn (10 phút). Tìm lại tướng nhé!")
            return
        if author_id != orig_author:
            bot._reply(snap, "⚠️ Chỉ người tìm kiếm mới được chọn số!")
            return
        bot._reply(snap, f"⏳ Đang tải skin #{keyword}...")
        threading.Thread(target=_process_skin, args=(bot, snap, slug, int(keyword)), daemon=True).start()
        return

    # Tìm tướng mới
    bot._reply(snap, f"⏳ Đang tìm tướng '{keyword}'...")
    threading.Thread(target=_process_init, args=(bot, snap, keyword), daemon=True).start()
