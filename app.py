"""
app.py — FBBot Dashboard với hệ thống phân quyền
Roles: owner > admin > ndh > member
"""
from __future__ import annotations
import json, os, sys, threading, time, traceback, importlib, hashlib, secrets
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, session

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _core._session import dataGetHome
from _messaging._send import api as SendAPI
from _messaging._listening import listeningEvent

# ---------------------------------------------------------------------------
# Paths & Globals
# ---------------------------------------------------------------------------
CONFIG_PATH   = HERE / "config.json"
USERS_PATH    = HERE / "users.json"
MODULES_DIR   = HERE / "modules"
DISABLED_PATH = HERE / "disabled_cmds.json"

LOG_BUFFER: list[dict] = []
CHAT_MESSAGES: dict[str, list[dict]] = {}
THREADS_META:  dict[str, dict] = {}
ANNOUNCEMENTS: list[dict] = []
BOT_STATUS = {"running": False, "uid": None, "start_time": None}
DISABLED_CMDS: set[str] = set()
ALL_COMMANDS = ["ping","help","id","echo","search","unsend","pin","love","ff","lq","kb"]

ROLES = ["owner","admin","ndh","member"]
ROLE_LEVEL = {"owner":4,"admin":3,"ndh":2,"member":1}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log(tag, msg, level="info"):
    line = {"ts": datetime.now().strftime("%H:%M:%S"), "tag": tag, "msg": msg, "level": level}
    print(f"[{line['ts']}] [{tag}] {msg}", flush=True)
    LOG_BUFFER.append(line)
    if len(LOG_BUFFER) > 300: LOG_BUFFER.pop(0)

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def load_users() -> dict:
    if not USERS_PATH.exists():
        default = {"quockhanh": {"password": hash_pw("zitcte"), "uid": "260729", "role": "admin", "created_at": "2026-06-05"}}
        USERS_PATH.write_text(json.dumps(default, indent=2, ensure_ascii=False))
    data = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    # migrate plaintext passwords
    changed = False
    for u, d in data.items():
        pw = d.get("password","")
        if pw and len(pw) != 64:
            d["password"] = hash_pw(pw)
            changed = True
    if changed: USERS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data

def save_users(data): USERS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {"cookies":"","prefix":"/","admins":[]}
def load_config():
    if not CONFIG_PATH.exists(): CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG,indent=2,ensure_ascii=False))
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for k,v in DEFAULT_CONFIG.items(): cfg.setdefault(k,v)
    return cfg
def save_config(cfg): CONFIG_PATH.write_text(json.dumps(cfg,indent=2,ensure_ascii=False))

def load_disabled():
    global DISABLED_CMDS
    if DISABLED_PATH.exists(): DISABLED_CMDS = set(json.loads(DISABLED_PATH.read_text()))
def save_disabled(): DISABLED_PATH.write_text(json.dumps(list(DISABLED_CMDS)))
load_disabled()

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def current_user():
    username = session.get("username")
    if not username: return None
    users = load_users()
    if username not in users: return None
    u = dict(users[username])
    u["username"] = username
    u.pop("password", None)
    return u

def require_role(min_role):
    """Decorator kiểm tra quyền tối thiểu."""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def wrapper(*args, **kwargs):
            u = current_user()
            if not u: return jsonify({"ok":False,"msg":"Chưa đăng nhập.","auth":False}), 401
            if ROLE_LEVEL.get(u["role"],0) < ROLE_LEVEL.get(min_role,0):
                return jsonify({"ok":False,"msg":"Không đủ quyền."}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------
class SimpleBot:
    def __init__(self, dataFB, prefix="/", admins=None):
        self.dataFB  = dataFB
        self.prefix  = prefix
        self.admins  = set(map(str, admins or []))
        self.sender  = SendAPI()
        self.listener = listeningEvent(dataFB)
        self._last_mid = None
        self._last_bot_msg = {}
        self._load_handlers()

    def _load_handlers(self):
        self._handlers = {}
        for name in ALL_COMMANDS:
            try:
                mod = importlib.import_module(f"modules.{name}")
                self._handlers[name] = mod.handle
            except Exception as e:
                log("bot", f"Không load {name}: {e}", "warn")

    def run(self):
        log("bot", f"UID = {self.dataFB.get('FacebookID')}")
        BOT_STATUS.update({"running":True,"uid":self.dataFB.get("FacebookID"),"start_time":time.time()})
        self.listener.get_last_seq_id()
        threading.Thread(target=self.listener.connect_mqtt, daemon=True).start()
        log("bot", "Listener ✓")
        while BOT_STATUS["running"]:
            self._poll()
            time.sleep(0.3)

    def stop(self):
        BOT_STATUS["running"] = False
        log("bot", "Bot dừng.")

    def _poll(self):
        snap = self.listener.bodyResults
        mid  = snap.get("messageID")
        body = snap.get("body","")
        if not mid or mid == self._last_mid: return
        self._last_mid = mid
        sender_id = str(snap.get("userID") or "")
        thread_id = str(snap.get("replyToID") or "")
        bot_id    = str(self.dataFB.get("FacebookID"))
        ts        = snap.get("timestamp", int(time.time()*1000))

        # Lấy tên người gửi (nếu có)
        sender_name = snap.get("senderName") or snap.get("authorName") or f"UID:{sender_id}"

        msg_obj = {"id":mid,"sender":sender_id,"sender_name":sender_name,
                   "body":body or "","ts":ts,"from_bot":sender_id==bot_id}
        if thread_id:
            CHAT_MESSAGES.setdefault(thread_id,[]).append(msg_obj)
            if len(CHAT_MESSAGES[thread_id])>200: CHAT_MESSAGES[thread_id].pop(0)
            prev = THREADS_META.get(thread_id,{})
            THREADS_META[thread_id] = {
                "id":thread_id,"last_msg":body or "","last_ts":ts,
                "name":prev.get("name", f"Thread {thread_id[-6:]}"),
                "last_sender":sender_name,
            }

        if not body or sender_id == bot_id: return
        if not body.startswith(self.prefix): return
        parts = body[len(self.prefix):].strip().split(maxsplit=1)
        if not parts: return
        cmd = parts[0].lower()
        arg = parts[1] if len(parts)>1 else ""
        if cmd in DISABLED_CMDS: return
        handler = self._handlers.get(cmd)
        if not handler: return
        log("cmd", f"/{cmd} từ {sender_id}")
        try: handler(self, snap, arg)
        except Exception as e: log("err", f"/{cmd}: {e}", "error")

    def send_message(self, thread_id, content):
        try:
            result = self.sender.send(self.dataFB, content, thread_id)
            ok = isinstance(result,dict) and result.get("success")==1
            if ok:
                mid = result.get("payload",{}).get("messageID","")
                CHAT_MESSAGES.setdefault(thread_id,[]).append({
                    "id":mid,"sender":str(self.dataFB.get("FacebookID")),
                    "sender_name":"Bot","body":content,
                    "ts":int(time.time()*1000),"from_bot":True,
                })
                THREADS_META.setdefault(thread_id,{"id":thread_id,"name":f"Thread {thread_id[-6:]}","last_ts":0})
                THREADS_META[thread_id].update({"last_msg":content,"last_ts":int(time.time()*1000),"last_sender":"Bot"})
                log("send",f"→ {thread_id}: {content!r}")
            return ok
        except Exception as e:
            log("err",f"Gửi: {e}","error"); return False

    def _reply(self, snap, content):
        thread_id = snap["replyToID"]
        type_chat = "user" if snap.get("type")=="user" else None
        result = self.sender.send(self.dataFB,content,thread_id,
                                  typeChat=type_chat,replyMessage=True,messageID=snap.get("messageID"))
        if isinstance(result,dict) and result.get("success")==1:
            try: self._last_bot_msg[str(thread_id)] = result["payload"]["messageID"]
            except: pass
            log("send",f"→ {thread_id}: {content!r}")
        else:
            log("send",f"FAIL: {result}","warn")

_bot: SimpleBot | None = None

def start_bot():
    global _bot
    if BOT_STATUS["running"]: return False,"Bot đang chạy."
    cfg = load_config()
    if not cfg.get("cookies") or len(cfg["cookies"])<20: return False,"Chưa có cookie."
    try:
        log("boot","Lấy session…")
        dataFB = dataGetHome(cfg["cookies"])
        if not dataFB.get("FacebookID"): return False,"Cookie hết hạn."
        _bot = SimpleBot(dataFB,prefix=cfg["prefix"],admins=cfg["admins"])
        threading.Thread(target=_bot.run,daemon=True).start()
        return True,f"Bot khởi động! UID: {dataFB.get('FacebookID')}"
    except Exception as e:
        log("err",str(e),"error"); return False,f"Lỗi: {e}"

def stop_bot():
    global _bot
    if not BOT_STATUS["running"]: return False,"Bot không chạy."
    if _bot: _bot.stop()
    _bot = None
    return True,"Bot đã dừng."

# ---------------------------------------------------------------------------
# Flask
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder="web/static")
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# ---- AUTH ----
@app.route("/")
def index():
    return send_from_directory("web","index.html")

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True) or {}
    username = data.get("username","").strip()
    password = data.get("password","")
    users = load_users()
    if username not in users:
        return jsonify({"ok":False,"msg":"Sai tên đăng nhập hoặc mật khẩu."})
    u = users[username]
    pw_hash = hash_pw(password)
    if u["password"] != pw_hash:
        return jsonify({"ok":False,"msg":"Sai tên đăng nhập hoặc mật khẩu."})
    session["username"] = username
    session.permanent = True
    return jsonify({"ok":True,"msg":"Đăng nhập thành công!",
                    "role":u["role"],"uid":u.get("uid",""),"username":username})

@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok":True})

@app.route("/api/auth/me")
def api_me():
    u = current_user()
    if not u: return jsonify({"ok":False,"auth":False}),401
    return jsonify({"ok":True,"auth":True,**u})

# ---- STATUS ----
@app.route("/api/status")
@require_role("member")
def api_status():
    uptime = int(time.time()-BOT_STATUS["start_time"]) if BOT_STATUS["start_time"] and BOT_STATUS["running"] else 0
    return jsonify({"running":BOT_STATUS["running"],"uid":BOT_STATUS["uid"],"uptime":uptime})

@app.route("/api/logs")
@require_role("ndh")
def api_logs():
    n = int(request.args.get("n",100))
    return jsonify({"logs":LOG_BUFFER[-n:]})

# ---- BOT CONTROL (owner/admin) ----
@app.route("/api/start", methods=["POST"])
@require_role("admin")
def api_start():
    ok,msg = start_bot(); return jsonify({"ok":ok,"msg":msg})

@app.route("/api/stop", methods=["POST"])
@require_role("admin")
def api_stop():
    ok,msg = stop_bot(); return jsonify({"ok":ok,"msg":msg})

# ---- CONFIG (owner only) ----
@app.route("/api/config", methods=["GET"])
@require_role("owner")
def api_config_get():
    cfg = load_config()
    safe = dict(cfg)
    if safe.get("cookies") and len(safe["cookies"])>20:
        safe["cookies_hint"] = safe["cookies"][:12]+"…(đã lưu)"
    safe["cookies"] = ""
    return jsonify(safe)

@app.route("/api/config", methods=["POST"])
@require_role("owner")
def api_config_save():
    data = request.get_json(force=True) or {}
    cfg  = load_config()
    if data.get("cookies"): cfg["cookies"] = data["cookies"]
    if "prefix" in data: cfg["prefix"] = data["prefix"] or "/"
    if "admins" in data:
        raw = data["admins"]
        cfg["admins"] = [x.strip() for x in raw.split(",") if x.strip()] if isinstance(raw,str) else raw
    save_config(cfg)
    log("web","Config cập nhật.")
    return jsonify({"ok":True,"msg":"Đã lưu!"})

# ---- COMMANDS (admin+) ----
@app.route("/api/commands")
@require_role("member")
def api_commands():
    u = current_user()
    role_level = ROLE_LEVEL.get(u["role"],0)
    cmds = []
    for name in ALL_COMMANDS:
        cmds.append({"name":name,"enabled":name not in DISABLED_CMDS,
                     "exists":(MODULES_DIR/f"{name}.py").exists(),
                     "can_toggle": role_level >= ROLE_LEVEL["admin"]})
    return jsonify({"commands":cmds})

@app.route("/api/commands/<name>/toggle", methods=["POST"])
@require_role("admin")
def api_toggle(name):
    if name not in ALL_COMMANDS: return jsonify({"ok":False,"msg":"Không tồn tại."})
    if name in DISABLED_CMDS: DISABLED_CMDS.discard(name); enabled=True
    else: DISABLED_CMDS.add(name); enabled=False
    save_disabled()
    return jsonify({"ok":True,"enabled":enabled,"msg":f"{'Bật' if enabled else 'Tắt'} /{name}"})

# ---- MODULES (admin+) ----
@app.route("/api/modules")
@require_role("admin")
def api_modules():
    files=[]
    for f in sorted(MODULES_DIR.glob("*.py")):
        if f.name.startswith("_"): continue
        files.append({"name":f.stem,"filename":f.name,"size":f.stat().st_size})
    return jsonify({"files":files})

@app.route("/api/modules/<name>", methods=["GET"])
@require_role("admin")
def api_module_get(name):
    path = MODULES_DIR/f"{name}.py"
    if not path.exists(): return jsonify({"ok":False,"msg":"Không tồn tại."})
    return jsonify({"ok":True,"content":path.read_text(encoding="utf-8")})

@app.route("/api/modules/<name>", methods=["POST"])
@require_role("admin")
def api_module_save(name):
    if not name.isidentifier(): return jsonify({"ok":False,"msg":"Tên không hợp lệ."})
    data = request.get_json(force=True) or {}
    (MODULES_DIR/f"{name}.py").write_text(data.get("content",""),encoding="utf-8")
    if _bot:
        try:
            mod = importlib.import_module(f"modules.{name}")
            importlib.reload(mod)
            _bot._handlers[name] = mod.handle
            if name not in ALL_COMMANDS: ALL_COMMANDS.append(name)
        except Exception as e: log("web",f"Reload lỗi: {e}","warn")
    log("web",f"{name}.py đã lưu.")
    return jsonify({"ok":True,"msg":f"Đã lưu {name}.py"})

@app.route("/api/modules/<name>", methods=["DELETE"])
@require_role("admin")
def api_module_delete(name):
    path = MODULES_DIR/f"{name}.py"
    if not path.exists(): return jsonify({"ok":False,"msg":"Không tồn tại."})
    path.unlink()
    if _bot and name in _bot._handlers: del _bot._handlers[name]
    return jsonify({"ok":True,"msg":f"Đã xóa {name}.py"})

# ---- CHAT ----
@app.route("/api/threads")
@require_role("member")
def api_threads():
    threads = sorted(THREADS_META.values(),key=lambda x:x.get("last_ts",0),reverse=True)
    return jsonify({"threads":threads})

@app.route("/api/threads/<thread_id>/messages")
@require_role("member")
def api_messages(thread_id):
    return jsonify({"messages":CHAT_MESSAGES.get(thread_id,[])[-100:]})

@app.route("/api/threads/<thread_id>/send", methods=["POST"])
@require_role("ndh")
def api_send(thread_id):
    if not _bot or not BOT_STATUS["running"]:
        return jsonify({"ok":False,"msg":"Bot chưa chạy."})
    data = request.get_json(force=True) or {}
    content = data.get("content","").strip()
    if not content: return jsonify({"ok":False,"msg":"Nội dung trống."})
    ok = _bot.send_message(thread_id,content)
    return jsonify({"ok":ok,"msg":"Đã gửi!" if ok else "Gửi thất bại."})

@app.route("/api/threads/<thread_id>/name", methods=["POST"])
@require_role("ndh")
def api_rename_thread(thread_id):
    data = request.get_json(force=True) or {}
    name = data.get("name","").strip()
    if thread_id in THREADS_META:
        THREADS_META[thread_id]["name"] = name or f"Thread {thread_id[-6:]}"
    return jsonify({"ok":True})

# ---- ANNOUNCEMENTS (admin+) ----
@app.route("/api/announcements")
@require_role("member")
def api_announcements_get():
    return jsonify({"announcements":ANNOUNCEMENTS[-50:]})

@app.route("/api/announcements", methods=["POST"])
@require_role("admin")
def api_announcements_post():
    u = current_user()
    data = request.get_json(force=True) or {}
    content = data.get("content","").strip()
    if not content: return jsonify({"ok":False,"msg":"Nội dung trống."})
    ann = {
        "id": int(time.time()*1000),
        "content": content,
        "author": u["username"],
        "role": u["role"],
        "ts": datetime.now().strftime("%H:%M %d/%m/%Y"),
    }
    ANNOUNCEMENTS.append(ann)
    log("web",f"Thông báo từ {u['username']}: {content}")
    return jsonify({"ok":True,"msg":"Đã đăng thông báo!"})

@app.route("/api/announcements/<int:ann_id>", methods=["DELETE"])
@require_role("admin")
def api_announcements_delete(ann_id):
    global ANNOUNCEMENTS
    ANNOUNCEMENTS = [a for a in ANNOUNCEMENTS if a["id"] != ann_id]
    return jsonify({"ok":True})

# ---- USERS (owner only) ----
@app.route("/api/users")
@require_role("owner")
def api_users_get():
    users = load_users()
    result = []
    for username, d in users.items():
        result.append({"username":username,"uid":d.get("uid",""),"role":d.get("role","member"),"created_at":d.get("created_at","")})
    return jsonify({"users":result})

@app.route("/api/users", methods=["POST"])
@require_role("owner")
def api_users_create():
    data = request.get_json(force=True) or {}
    username = data.get("username","").strip()
    password = data.get("password","").strip()
    uid      = data.get("uid","").strip()
    role     = data.get("role","member")
    if not username or not password: return jsonify({"ok":False,"msg":"Thiếu tên hoặc mật khẩu."})
    if not username.isidentifier(): return jsonify({"ok":False,"msg":"Tên không hợp lệ."})
    if role not in ROLES: return jsonify({"ok":False,"msg":"Role không hợp lệ."})
    users = load_users()
    if username in users: return jsonify({"ok":False,"msg":"Tên đã tồn tại."})
    users[username] = {"password":hash_pw(password),"uid":uid,"role":role,"created_at":datetime.now().strftime("%Y-%m-%d")}
    save_users(users)
    log("web",f"Tạo tài khoản: {username} ({role})")
    return jsonify({"ok":True,"msg":f"Đã tạo tài khoản {username}!"})

@app.route("/api/users/<username>", methods=["PATCH"])
@require_role("owner")
def api_users_update(username):
    u = current_user()
    data = request.get_json(force=True) or {}
    users = load_users()
    if username not in users: return jsonify({"ok":False,"msg":"Không tìm thấy."})
    if "role" in data:
        new_role = data["role"]
        if new_role not in ROLES: return jsonify({"ok":False,"msg":"Role không hợp lệ."})
        # Không ai nâng lên owner ngoài owner gốc
        if new_role == "owner" and u.get("role") != "owner":
            return jsonify({"ok":False,"msg":"Chỉ owner mới có thể trao quyền owner."})
        users[username]["role"] = new_role
    if data.get("password"):
        users[username]["password"] = hash_pw(data["password"])
    if "uid" in data:
        users[username]["uid"] = data["uid"]
    save_users(users)
    return jsonify({"ok":True,"msg":f"Đã cập nhật {username}."})

@app.route("/api/users/<username>", methods=["DELETE"])
@require_role("owner")
def api_users_delete(username):
    u = current_user()
    if username == u["username"]: return jsonify({"ok":False,"msg":"Không thể xóa tài khoản của chính mình."})
    users = load_users()
    if username not in users: return jsonify({"ok":False,"msg":"Không tìm thấy."})
    del users[username]
    save_users(users)
    return jsonify({"ok":True,"msg":f"Đã xóa {username}."})

@app.route("/api/users/change-password", methods=["POST"])
@require_role("member")
def api_change_password():
    u = current_user()
    data = request.get_json(force=True) or {}
    old_pw = data.get("old_password","")
    new_pw = data.get("new_password","")
    if not old_pw or not new_pw: return jsonify({"ok":False,"msg":"Thiếu thông tin."})
    users = load_users()
    if users[u["username"]]["password"] != hash_pw(old_pw):
        return jsonify({"ok":False,"msg":"Mật khẩu cũ không đúng."})
    users[u["username"]]["password"] = hash_pw(new_pw)
    save_users(users)
    return jsonify({"ok":True,"msg":"Đã đổi mật khẩu!"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    log("web",f"Dashboard: http://0.0.0.0:{port}")
    app.run(host="0.0.0.0",port=port,debug=False,use_reloader=False)
