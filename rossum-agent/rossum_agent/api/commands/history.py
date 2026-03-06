from __future__ import annotations

from datetime import UTC, datetime

from rossum_agent.api.commands.registry import CommandContext, register_command


async def handle_history(ctx: CommandContext) -> str:
    if ctx.args:
        try:
            limit = int(ctx.args[0])
        except ValueError:
            return f"Invalid limit `{ctx.args[0]}`. Usage: `/history` or `/history <number>`"
    else:
        limit = 20

    response = ctx.chat_service.list_chats(user_id=ctx.user_id, limit=limit + 1)
    chats = [chat for chat in response.chats if chat.chat_id != ctx.chat_id][:limit]

    if not chats:
        return "No past chats found."

    lines = [f"**Past chats ({len(chats)}):**", ""]
    for chat in chats:
        timestamp = datetime.fromtimestamp(chat.timestamp, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        label = chat.summary or chat.preview or chat.first_message or "(empty)"
        if len(label) > 80:
            label = label[:77] + "..."
        lines.append(f"- **{timestamp}** - {label} ({chat.message_count} messages)")

    return "\n".join(lines)


register_command("/history", "Show past chat sessions", handle_history)
