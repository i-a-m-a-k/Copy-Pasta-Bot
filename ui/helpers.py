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


