import io
import asyncio
import urllib.parse
from typing import Optional, Union
import aiohttp
import discord

from ui.embeds import error_embed, warning_embed
from ui.helpers import get_http_session

CATAAS_BASE_URL = "https://cataas.com"
CATAAS_USER_AGENT = "CopyPastaBot Discord"
CATAAS_TIMEOUT = aiohttp.ClientTimeout(total=20)


def parse_cat_args(args: list[str]) -> tuple[bool, Optional[str], Optional[str]]:
	"""
	Parses flags and text for the ;;cat command.
	Flags:
	  -g, --gif : Generate animated GIF
	  -t, --tag <tag> : Fetch cat with a specific tag
	Remaining tokens are joined as the caption text.
	Returns (is_gif, tag, text).
	"""
	tokens = args[1:] if len(args) > 1 else []
	is_gif = False
	tag: Optional[str] = None
	text_words: list[str] = []

	i = 0
	while i < len(tokens):
		token = tokens[i]
		if token in ('-g', '--gif'):
			is_gif = True
			i += 1
		elif token in ('-t', '--tag'):
			if i + 1 < len(tokens):
				tag = tokens[i + 1].strip().lower()
				i += 2
			else:
				i += 1
		elif token.startswith('-t='):
			tag = token[3:].strip().lower()
			i += 1
		elif token.startswith('--tag='):
			tag = token[6:].strip().lower()
			i += 1
		else:
			text_words.append(token)
			i += 1

	text = ' '.join(text_words).strip() if text_words else None
	return is_gif, tag, text


def build_cat_url(is_gif: bool, tag: Optional[str], text: Optional[str]) -> str:
	"""Builds the Cataas API URL based on gif mode, tag, and caption text."""
	encoded_text = urllib.parse.quote(text) if text else None
	encoded_tag = urllib.parse.quote(tag) if tag else None

	if is_gif:
		if encoded_text and encoded_tag:
			return f"{CATAAS_BASE_URL}/cat/gif/says/{encoded_text}?tag={encoded_tag}"
		elif encoded_text:
			return f"{CATAAS_BASE_URL}/cat/gif/says/{encoded_text}"
		elif encoded_tag:
			return f"{CATAAS_BASE_URL}/cat/gif?tag={encoded_tag}"
		else:
			return f"{CATAAS_BASE_URL}/cat/gif"
	else:
		if encoded_text and encoded_tag:
			return f"{CATAAS_BASE_URL}/cat/{encoded_tag}/says/{encoded_text}"
		elif encoded_text:
			return f"{CATAAS_BASE_URL}/cat/says/{encoded_text}"
		elif encoded_tag:
			return f"{CATAAS_BASE_URL}/cat/{encoded_tag}"
		else:
			return f"{CATAAS_BASE_URL}/cat"


async def fetch_cat_media(
	is_gif: bool,
	tag: Optional[str],
	text: Optional[str]
) -> tuple[Optional[io.BytesIO], Optional[str], Optional[discord.Embed]]:
	"""
	Fetches a cat image or GIF from Cataas.
	Returns (image_buffer, filename, error_embed).
	"""
	session = await get_http_session()
	headers = {"User-Agent": CATAAS_USER_AGENT}
	url = build_cat_url(is_gif, tag, text)

	async with session.get(url, headers=headers, timeout=CATAAS_TIMEOUT) as resp:
		if resp.status == 404:
			if tag:
				return None, None, warning_embed(
					f"No cat found with tag `{tag}`.",
					title="🐱 No Cat Found"
				)
			return None, None, warning_embed("Cat not found on Cataas.", title="🐱 No Cat Found")

		if resp.status != 200:
			return None, None, error_embed(
				f"Failed to fetch cat from Cataas (HTTP {resp.status}).",
				title="❌ Cataas Error"
			)

		content_type = resp.headers.get("Content-Type", "").lower()
		if "gif" in content_type or is_gif:
			filename = "cat.gif"
		elif "png" in content_type:
			filename = "cat.png"
		elif "webp" in content_type:
			filename = "cat.webp"
		else:
			filename = "cat.jpg"

		media_bytes = await resp.read()

	buffer = io.BytesIO(media_bytes)
	buffer.seek(0)
	return buffer, filename, None


async def handle_cat(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None,
	message: Optional[discord.Message] = None
) -> Union[discord.File, discord.Embed]:
	"""
	Handles the ;;cat command.
	Fetches cat images or GIFs with optional tags (-t <tag>) and text captions.
	"""
	is_gif, tag, text = parse_cat_args(args)

	# If no text was provided in args, check if user replied to a message with text
	if not text and reply and hasattr(reply, 'resolved') and reply.resolved and getattr(reply.resolved, 'content', None):
		text = reply.resolved.content.strip()

	try:
		buffer, filename, err_embed = await fetch_cat_media(is_gif, tag, text)
		if err_embed:
			return err_embed
		if buffer is None or filename is None:
			return error_embed("An unexpected error occurred while fetching your cat.", title="❌ Error")

		return discord.File(buffer, filename=filename)

	except (asyncio.TimeoutError, TimeoutError):
		return error_embed("Request to Cataas timed out. Please try again.", title="⏱️ Timeout")
	except aiohttp.ClientError as e:
		return error_embed(f"Network error communicating with Cataas: {e}", title="🌐 Network Error")
	except Exception as e:
		return error_embed(f"Failed to fetch cat: {e}", title="❌ Error")
