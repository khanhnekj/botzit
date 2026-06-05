from _features._facebook import _search

def handle(bot, snap: dict, arg: str) -> None:
    if not arg:
        bot._reply(snap, f"Cách dùng: {bot.prefix}search <từ khoá>")
        return
    try:
        res = _search.func(bot.dataFB, arg)
    except Exception as exc:  # noqa: BLE001
        bot._reply(snap, f"❌ Lỗi tìm kiếm: {exc}")
        return

    users = res.get("searchResultsDict") if isinstance(res, dict) else None
    if not users:
        bot._reply(snap, f"🔍 Không tìm thấy kết quả nào cho: {arg}")
        return

    lines = [f"🔍 Kết quả cho “{arg}”:"]
    for i, u in enumerate(users[:5], 1):
        lines.append(f"{i}. {u.get('name')} — {u.get('id')}")
    bot._reply(snap, "\n".join(lines))
