import os
import io
import re
import json
import tempfile
import asyncio
from typing import Optional, Union
import aiohttp
import discord

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
SUPPORTED_VIDEO_EXTENSIONS = ('.mp4', '.mov', '.webm', '.mkv', '.avi')
SUPPORTED_VIDEO_MIMES = ('video/mp4', 'video/quicktime', 'video/webm', 'video/x-matroska', 'video/x-msvideo')

def is_image_attachment(attachment: discord.Attachment) -> bool:
	"""Check if a Discord attachment is a supported image format."""
	if hasattr(attachment, 'content_type') and attachment.content_type:
		if attachment.content_type in SUPPORTED_IMAGE_MIMES or attachment.content_type.startswith('image/'):
			return True
	filename = getattr(attachment, 'filename', '').lower()
	return filename.endswith(SUPPORTED_IMAGE_EXTENSIONS)

def is_video_attachment(attachment: discord.Attachment) -> bool:
	"""Check if a Discord attachment is a supported video format."""
	if hasattr(attachment, 'content_type') and attachment.content_type:
		if attachment.content_type in SUPPORTED_VIDEO_MIMES or attachment.content_type.startswith('video/'):
			return True
	filename = getattr(attachment, 'filename', '').lower()
	return filename.endswith(SUPPORTED_VIDEO_EXTENSIONS)

def guess_video_mime_type(url: str) -> str:
	"""Infer a video/* MIME type from a URL's file extension (defaults to video/mp4)."""
	ext = os.path.splitext(url.split('?')[0].lower())[1]
	return {
		'.mp4': 'video/mp4',
		'.mov': 'video/quicktime',
		'.webm': 'video/webm',
		'.mkv': 'video/x-matroska',
		'.avi': 'video/x-msvideo',
	}.get(ext, 'video/mp4')

# Maximum allowed video file size for AI generation source input (50 MB).
# Luma API has practical limits; this prevents abuse and wasted API credits.
MAX_VIDEO_SOURCE_SIZE = 50 * 1024 * 1024  # 50 MB

# Maximum allowed download size for images fetched for processing (25 MB).
MAX_IMAGE_DOWNLOAD_SIZE = 25 * 1024 * 1024  # 25 MB

# Allowed domains for outbound HTTP requests (SSRF protection).
# Only Discord CDN domains are permitted for media fetching.
ALLOWED_CDN_DOMAINS = frozenset({
	'cdn.discordapp.com',
	'media.discordapp.net',
})

def _is_allowed_url(url: str) -> bool:
	"""Check if a URL belongs to an allowed CDN domain (SSRF protection)."""
	from urllib.parse import urlparse
	try:
		parsed = urlparse(url)
		return parsed.hostname in ALLOWED_CDN_DOMAINS if parsed.hostname else False
	except Exception:
		return False

async def validate_video_url(url: str) -> tuple[bool, Optional[str], Optional[str]]:
	"""
	Validates a video URL before sending it to an external AI API.
	Performs a lightweight HEAD request to verify:
	- URL is reachable (HTTP 200)
	- Content-Type is actually video/*
	- Content-Length is within MAX_VIDEO_SOURCE_SIZE

	Returns (is_valid, mime_type, error_message).
	On success: (True, mime_type_string, None)
	On failure: (False, None, human_readable_error)
	"""
	if not _is_allowed_url(url):
		return False, None, "Video URL must be from Discord's CDN."
	try:
		session = await get_http_session()
		async with session.head(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True) as resp:
			if resp.status != 200:
				return False, None, f"Could not access the video (HTTP {resp.status})."

			content_type = (resp.headers.get('Content-Type') or '').lower()
			if not content_type.startswith('video/'):
				return False, None, f"The linked file is not a video (detected type: `{content_type or 'unknown'}`)."

			content_length = resp.headers.get('Content-Length')
			if content_length is not None:
				size_bytes = int(content_length)
				if size_bytes > MAX_VIDEO_SOURCE_SIZE:
					size_mb = size_bytes / (1024 * 1024)
					limit_mb = MAX_VIDEO_SOURCE_SIZE / (1024 * 1024)
					return False, None, f"Video is too large ({size_mb:.1f} MB). Maximum allowed: {limit_mb:.0f} MB."
			else:
				# No Content-Length header: cannot verify size upfront.
				# Proceed but log a warning.
				print(f"Warning: No Content-Length for video URL, size unverified: {url[:100]}")

			return True, content_type, None

	except asyncio.TimeoutError:
		return False, None, "Timed out while checking the video URL."
	except Exception as e:
		return False, None, f"Failed to validate video: {e}"

def extract_media_urls(
	reply: Optional[Union[discord.MessageReference, discord.Message]] = None,
	message: Optional[discord.Message] = None
) -> tuple[list[str], list[str]]:
	"""
	Extract ALL image and video URLs from a replied-to message (priority),
	falling back to the command message itself.
	Returns (image_urls, video_urls) preserving attachment order.
	"""
	replied_msg = None
	if reply is not None:
		if isinstance(reply, discord.Message) or hasattr(reply, 'attachments'):
			replied_msg = reply
		elif hasattr(reply, 'resolved') and reply.resolved is not None:
			replied_msg = reply.resolved

	sources = [m for m in (replied_msg, message) if m is not None]

	image_urls: list[str] = []
	video_urls: list[str] = []

	for src in sources:
		if hasattr(src, 'attachments') and src.attachments:
			for att in src.attachments:
				if is_image_attachment(att):
					image_urls.append(att.url)
				elif is_video_attachment(att):
					video_urls.append(att.url)
		if hasattr(src, 'embeds') and src.embeds:
			for emb in src.embeds:
				if emb.image and emb.image.url:
					image_urls.append(emb.image.url)
				elif emb.thumbnail and emb.thumbnail.url:
					image_urls.append(emb.thumbnail.url)
				if emb.video and emb.video.url:
					video_urls.append(emb.video.url)
		# Replied message has priority: only fall through to the command
		# message if nothing was found on the replied message.
		if image_urls or video_urls:
			break

	return image_urls, video_urls

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
	if not _is_allowed_url(url):
		return None, "Image URL must be from Discord's CDN."
	try:
		session = await get_http_session()
		async with session.get(url) as response:
			if response.status != 200:
				return None, f"Failed to download image from Discord CDN (HTTP {response.status})"
			# Read with size limit to prevent memory exhaustion
			data = await response.read()
			if len(data) > MAX_IMAGE_DOWNLOAD_SIZE:
				size_mb = len(data) / (1024 * 1024)
				limit_mb = MAX_IMAGE_DOWNLOAD_SIZE / (1024 * 1024)
				return None, f"Image too large ({size_mb:.1f} MB). Maximum: {limit_mb:.0f} MB."
			return data, None
	except Exception as e:
		return None, f"Network error downloading image: {str(e)}"


# --- Sticker Media & Lottie Handling ---

LOTTIE_STICKER_REGEX = re.compile(r'https?://(?:cdn|media)\.discordapp\.(?:com|net)/stickers/(\d+)\.json')
APNG_STICKER_REGEX = re.compile(r'https?://(?:cdn|media)\.discordapp\.(?:com|net)/stickers/(\d+)\.png')

def get_sticker_media_url(sticker: Union[discord.StickerItem, discord.GuildSticker], size: int = 240) -> str:
	"""
	Constructs the canonical Discord CDN URL for a sticker:
	- GIF: cdn.discordapp.com/stickers/{id}.gif
	- APNG: cdn.discordapp.com/stickers/{id}.png (converted lazily to animated GIF on first recall)
	- PNG: cdn.discordapp.com/stickers/{id}.png
	- Lottie: cdn.discordapp.com/stickers/{id}.json (converted lazily to animated GIF on first recall)
	"""
	format_type = getattr(sticker, 'format', None)
	sticker_id = getattr(sticker, 'id', '')

	if format_type == discord.StickerFormatType.gif:
		return f"https://cdn.discordapp.com/stickers/{sticker_id}.gif"
	elif format_type == discord.StickerFormatType.lottie:
		return f"https://cdn.discordapp.com/stickers/{sticker_id}.json"
	else:
		return f"https://cdn.discordapp.com/stickers/{sticker_id}.png"


def _sync_apng_to_gif(image_bytes: bytes) -> Optional[bytes]:
	"""
	Converts animated PNG (APNG) bytes to animated GIF bytes using Pillow.
	Returns None if the image is static or conversion fails.
	"""
	try:
		from PIL import Image, ImageSequence
		im = Image.open(io.BytesIO(image_bytes))
		if not getattr(im, 'is_animated', False) or getattr(im, 'n_frames', 1) <= 1:
			return None

		frames = []
		durations = []
		for frame in ImageSequence.Iterator(im):
			frames.append(frame.convert('RGBA'))
			durations.append(frame.info.get('duration', 100))

		if not frames:
			return None

		out = io.BytesIO()
		frames[0].save(
			out,
			format='GIF',
			save_all=True,
			append_images=frames[1:],
			duration=durations,
			loop=0,
			disposal=2
		)
		gif_data = out.getvalue()
		return gif_data if gif_data else None
	except Exception as e:
		print(f"APNG to GIF conversion error: {e}")
		return None


async def convert_apng_url_to_gif(url: str) -> Optional[bytes]:
	"""
	Downloads a PNG sticker from Discord CDN and converts it to animated GIF if it is an APNG.
	"""
	session = await get_http_session()
	try:
		async with session.get(url) as resp:
			if resp.status != 200:
				return None
			image_data = await resp.read()
		return await asyncio.to_thread(_sync_apng_to_gif, image_data)
	except Exception as e:
		print(f"Error fetching/converting APNG from {url}: {e}")
		return None


def _sync_lottie_to_gif(json_content: str) -> Optional[bytes]:
	"""
	Synchronous worker converting Lottie JSON text to animated GIF bytes.
	Tries pyrlottie first, then python-lottie.
	"""
	# 1. Try pyrlottie
	try:
		from pyrlottie import convMultLottie, FileMap, LottieFile, run
		with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False, encoding='utf-8') as tf_in:
			tf_in.write(json_content)
			in_path = tf_in.name
		out_path = in_path + '.gif'
		try:
			task = [FileMap(LottieFile(in_path), {out_path})]
			run(convMultLottie(task))
			if os.path.exists(out_path):
				with open(out_path, 'rb') as f:
					data = f.read()
				if data:
					return data
		finally:
			if os.path.exists(in_path):
				try:
					os.remove(in_path)
				except OSError:
					pass
			if os.path.exists(out_path):
				try:
					os.remove(out_path)
				except OSError:
					pass
	except ImportError:
		pass
	except Exception as e:
		print(f"pyrlottie conversion failed: {e}")

	# 2. Try python-lottie
	try:
		from lottie.exporters.gif import export_gif
		from lottie.objects import Animation
		data = json.loads(json_content)
		anim = Animation.load(data)
		out = io.BytesIO()
		export_gif(anim, out)
		gif_bytes = out.getvalue()
		if gif_bytes:
			return gif_bytes
	except ImportError:
		pass
	except Exception as e:
		print(f"python-lottie conversion failed: {e}")

	return None


async def convert_lottie_url_to_gif(url: str) -> Optional[bytes]:
	"""
	Downloads a Lottie .json file and converts it into animated GIF bytes.
	Runs CPU-bound rendering inside an asyncio worker thread.
	"""
	session = await get_http_session()
	try:
		async with session.get(url) as resp:
			if resp.status != 200:
				return None
			json_text = await resp.text()
		return await asyncio.to_thread(_sync_lottie_to_gif, json_text)
	except Exception as e:
		print(f"Error fetching/converting Lottie from {url}: {e}")
		return None


