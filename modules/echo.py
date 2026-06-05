def handle(bot, snap: dict, arg: str) -> None:
    if not arg:
        bot._reply(snap, f"Cách dùng: {bot.prefix}echo <nội dung>")
        return
    bot._reply(snap, arg)
