import random
import urllib.parse
from typing import Optional, Union
import discord

from ui.embeds import warning_embed

GOOGLE_SEARCH_BASE_URL = "https://www.google.com/search"

REPLY_PREFIXES = [
	"Don't bother other people. Use search.",
	"Let me Google that for you:",
	"Google is free, you know:",
	"Here, I did the research for you:",
	"Was that so hard? Here you go:",
	"Next time, try searching first:",
]


def build_lmgtfy_url(query: str) -> str:
	"""Constructs a Google search link with proper '+' space substitution and URL encoding."""
	encoded_query = urllib.parse.quote_plus(query.strip())
	return f"{GOOGLE_SEARCH_BASE_URL}?q={encoded_query}"


def handle_lmgtfy(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None,
	message: Optional[discord.Message] = None
) -> Union[str, discord.Embed]:
	"""
	Handles the ;;lmgtfy command.
	Constructs a Google search link using the provided arguments or the text of the replied message.
	When triggered as a reply, prepends a fun witty text before the link.
	"""
	is_reply = reply is not None and hasattr(reply, 'resolved') and reply.resolved is not None
	query = ' '.join(args[1:]).strip() if len(args) > 1 else ''

	# Fall back to replied message text if no explicit search query is provided in args
	if not query and is_reply and getattr(reply.resolved, 'content', None):
		query = reply.resolved.content.strip()

	if not query:
		if is_reply:
			return warning_embed("The message you replied to contains no text to search.", title="⚠️ No Text Found")
		return warning_embed("Please provide a search query or reply to a message.\nUsage: `;;lmgtfy <query>`", title="⚠️ Missing Query")

	url = build_lmgtfy_url(query)

	if is_reply:
		prefix = random.choice(REPLY_PREFIXES)
		return f"{prefix}\n{url}"

	return url


__all__ = ['build_lmgtfy_url', 'handle_lmgtfy', 'REPLY_PREFIXES']
