def handle(bot, snap: dict, arg: str) -> None:
    bot._reply(snap, (
        f"🆔 type      : {snap.get('type')}\n"
        f"   threadID  : {snap.get('replyToID')}\n"
        f"   userID    : {snap.get('userID')}\n"
        f"   messageID : {snap.get('messageID')}"
    ))
