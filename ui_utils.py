from typing import Optional, Union
import aiohttp
import discord

# --- Shared Embed Helpers ---

def success_embed(description: str, title: Optional[str] = None) -> discord.Embed:
	embed = discord.Embed(description=description, color=discord.Color.green())
	if title:
		embed.title = title
	return embed

def error_embed(description: str, title: Optional[str] = None) -> discord.Embed:
	embed = discord.Embed(description=description, color=discord.Color.red())
	if title:
		embed.title = title
	return embed

def warning_embed(description: str, title: Optional[str] = None) -> discord.Embed:
	embed = discord.Embed(description=description, color=discord.Color.gold())
	if title:
		embed.title = title
	return embed

def info_embed(description: str, title: Optional[str] = None) -> discord.Embed:
	embed = discord.Embed(description=description, color=discord.Color.blurple())
	if title:
		embed.title = title
	return embed


# --- Shared HTTP Session Management ---

_HTTP_SESSION: Optional[aiohttp.ClientSession] = None

async def get_http_session() -> aiohttp.ClientSession:
	"""Get or initialize the shared global aiohttp.ClientSession."""
	global _HTTP_SESSION
	if _HTTP_SESSION is None or _HTTP_SESSION.closed:
		_HTTP_SESSION = aiohttp.ClientSession()
	return _HTTP_SESSION

async def close_http_session():
	"""Close the shared global aiohttp.ClientSession gracefully on shutdown."""
	global _HTTP_SESSION
	if _HTTP_SESSION and not _HTTP_SESSION.closed:
		await _HTTP_SESSION.close()
		_HTTP_SESSION = None


# --- Unified Image / Attachment Extractor ---

SUPPORTED_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.tiff')
SUPPORTED_IMAGE_MIMES = ('image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/tiff')

def is_image_attachment(attachment: discord.Attachment) -> bool:
	"""Check if a Discord attachment is a supported image format."""
	if hasattr(attachment, 'content_type') and attachment.content_type:
		if attachment.content_type in SUPPORTED_IMAGE_MIMES or attachment.content_type.startswith('image/'):
			return True
	filename = getattr(attachment, 'filename', '').lower()
	return filename.endswith(SUPPORTED_IMAGE_EXTENSIONS)

def extract_image_url(
	reply: Optional[Union[discord.MessageReference, discord.Message]] = None,
	message: Optional[discord.Message] = None
) -> Optional[str]:
	"""
	Extract an image URL with intelligent priority fallback:
	1. Check attachments of the replied-to message
	2. Check image embeds of the replied-to message
	3. Check attachments of the command message itself
	4. Check image embeds of the command message itself
	"""
	# Normalize reply target message
	replied_msg = None
	if reply is not None:
		if isinstance(reply, discord.Message):
			replied_msg = reply
		elif hasattr(reply, 'resolved') and isinstance(reply.resolved, discord.Message):
			replied_msg = reply.resolved

	# Priority 1: Check replied-to message attachments
	if replied_msg and hasattr(replied_msg, 'attachments') and replied_msg.attachments:
		for att in replied_msg.attachments:
			if is_image_attachment(att):
				return att.url

	# Priority 2: Check replied-to message embeds
	if replied_msg and hasattr(replied_msg, 'embeds') and replied_msg.embeds:
		for emb in replied_msg.embeds:
			if emb.image and emb.image.url:
				return emb.image.url
			if emb.thumbnail and emb.thumbnail.url:
				return emb.thumbnail.url

	# Priority 3: Check command message attachments
	if message and hasattr(message, 'attachments') and message.attachments:
		for att in message.attachments:
			if is_image_attachment(att):
				return att.url

	# Priority 4: Check command message embeds
	if message and hasattr(message, 'embeds') and message.embeds:
		for emb in message.embeds:
			if emb.image and emb.image.url:
				return emb.image.url
			if emb.thumbnail and emb.thumbnail.url:
				return emb.thumbnail.url

	return None

async def fetch_image_bytes(url: str) -> tuple[Optional[bytes], Optional[str]]:
	"""
	Download image bytes using the shared aiohttp ClientSession.
	Returns (image_bytes, error_message).
	"""
	try:
		session = await get_http_session()
		async with session.get(url) as response:
			if response.status != 200:
				return None, f"Failed to download image from Discord CDN (HTTP {response.status})"
			data = await response.read()
			return data, None
	except Exception as e:
		return None, f"Network error downloading image: {str(e)}"
