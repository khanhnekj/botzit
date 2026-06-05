import time

def handle(bot, snap: dict, arg: str) -> None:
    sent_ts = int(snap.get("timestamp") or 0)
    if sent_ts:
        latency_ms = max(0, int(time.time() * 1000) - sent_ts)
        bot._reply(snap, f"🏓 pong! ({latency_ms} ms)")
    else:
        bot._reply(snap, "🏓 pong!")
