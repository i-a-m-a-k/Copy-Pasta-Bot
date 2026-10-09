import asyncio
import base64
import io
import re
from typing import Optional, Union
from PIL import Image
import discord
from ui.embeds import warning_embed
from .thonkify_dict import thonkifydict

MAX_THONKIFY_CHARS = 120
MAX_THONKIFY_LINES = 6
MAX_CHARS_PER_LINE = 20

# Tracking spacer image between adjacent characters (height: 896, width: 6)
_TRACKING_IMAGE = Image.open(io.BytesIO(base64.b64decode(
	'iVBORw0KGgoAAAANSUhEUgAAAAYAAAOACAYAAAAZzQIQAAAALElEQVR4nO3BAQ0AAADCoPdPbQ8HFAAAAAAAAAAAAAAAAAAAAAAAAAAAAPwZV4AAAfA8WFIAAAAASUVORK5CYII='
)))

# Space character image (height: 896, width: 180)
_SPACE_IMAGE = Image.new('RGBA', (180, 896), (0, 0, 0, 0))

def _wrap_text(text: str, max_chars: int = MAX_CHARS_PER_LINE) -> list[str]:
	"""Splits text into lines respecting explicit newlines and auto-wrapping long lines."""
	raw_lines = text.splitlines()
	wrapped_lines: list[str] = []

	for r_line in raw_lines:
		r_line = r_line.strip()
		if not r_line:
			continue
		words = r_line.split()
		curr_line: list[str] = []
		curr_len = 0

		for word in words:
			word_len = len(word)
			if curr_len + word_len + (1 if curr_line else 0) <= max_chars:
				curr_line.append(word)
				curr_len += word_len + (1 if curr_line else 0)
			else:
				if curr_line:
					wrapped_lines.append(' '.join(curr_line))
				while len(word) > max_chars:
					wrapped_lines.append(word[:max_chars])
					word = word[max_chars:]
				curr_line = [word] if word else []
				curr_len = len(word)

		if curr_line:
			wrapped_lines.append(' '.join(curr_line))

	return wrapped_lines[:MAX_THONKIFY_LINES]

def generate_thonkify(text: str) -> Optional[io.BytesIO]:
	"""
	Stitches thinking face (🤔) font glyphs across multiple lines.
	Only letters (A-Z, a-z) and spaces are thonkified; other characters are skipped.
	"""
	text = re.sub(r'<@!?\d+>', '@user', text)
	text = text.strip()

	lines = _wrap_text(text)
	if not lines:
		return None

	glyph_lines: list[tuple[list[Image.Image], int]] = []

	for line in lines:
		line_images: list[Image.Image] = []
		for c in line:
			if c == ' ':
				line_images.append(_SPACE_IMAGE)
			elif c in thonkifydict:
				line_images.append(thonkifydict[c])
				line_images.append(_TRACKING_IMAGE)
			elif c.upper() in thonkifydict:
				line_images.append(thonkifydict[c.upper()])
				line_images.append(_TRACKING_IMAGE)
			elif c.lower() in thonkifydict:
				line_images.append(thonkifydict[c.lower()])
				line_images.append(_TRACKING_IMAGE)

		# Remove trailing spacer from line
		if line_images and line_images[-1] is _TRACKING_IMAGE:
			line_images.pop()

		if line_images:
			line_width = sum(img.width for img in line_images)
			glyph_lines.append((line_images, line_width))

	if not glyph_lines:
		return None

	max_width = max(w for _, w in glyph_lines)
	line_height = 896
	line_spacing = 80
	total_height = len(glyph_lines) * line_height + (len(glyph_lines) - 1) * line_spacing

	canvas = Image.new('RGBA', (max_width, total_height), (0, 0, 0, 0))

	curr_y = 0
	for line_images, line_width in glyph_lines:
		curr_x = 0
		for img in line_images:
			mask = img.split()[-1] if img.mode == 'RGBA' else None
			canvas.paste(img, (curr_x, curr_y), mask=mask)
			curr_x += img.width
		curr_y += line_height + line_spacing

	# Downscale if dimensions exceed 3800px to maintain crisp rendering on Discord
	if canvas.width > 3800 or canvas.height > 3800:
		ratio = min(3800 / canvas.width, 3800 / canvas.height)
		new_size = (int(canvas.width * ratio), int(canvas.height * ratio))
		canvas = canvas.resize(new_size, Image.LANCZOS)

	buffer = io.BytesIO()
	canvas.save(buffer, format='PNG')
	buffer.seek(0)
	return buffer

async def handle_thonkify_command(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None,
	message: Optional[discord.Message] = None
) -> Union[discord.File, discord.Embed]:
	"""
	Handles the ;;thonkify command (letters only, with multi-line and length validation).
	"""
	text = ''
	if len(args) > 1:
		text = ' '.join(args[1:])
	elif reply and hasattr(reply, 'resolved') and reply.resolved and reply.resolved.content:
		text = reply.resolved.content

	if not text.strip():
		return warning_embed("Please reply to a message or provide text: `;;thonkify <your text>`", title="⚠️ No Text Provided")

	if len(text.strip()) > MAX_THONKIFY_CHARS:
		buffer = await asyncio.to_thread(generate_thonkify, "Thonk yourself")
		return discord.File(buffer, filename='thonk_yourself.png')

	buffer = await asyncio.to_thread(generate_thonkify, text)
	if buffer is None:
		buffer = await asyncio.to_thread(generate_thonkify, "Thonk yourself")
		return discord.File(buffer, filename='thonk_yourself.png')

	return discord.File(buffer, filename='thonkify.png')
