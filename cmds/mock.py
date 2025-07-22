import os
import re

import discord
from PIL import Image, ImageDraw, ImageFont

import constants
from Message import Message


def _get_asset_path(filename: str) -> str:
	root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	return os.path.join(root_dir, 'assets', filename)

def _process_text(message: discord.Message, content: str) -> list:

	# Create a mapping of user IDs to display names
	user_mentions = {
		str(user.id): user.display_name
		for user in message.mentions
	}

	segments = []
	current_pos = 0

	# Find all user mentions in the text
	for match in re.finditer(r'<@!?(\d+)>', content):
		user_id = match.group(1)

		# Add text before the mention
		if match.start() > current_pos:
			segments.append((content[current_pos:match.start()], True))

		# Add the mention with display name if found, otherwise keep original mention
		if user_id in user_mentions:
			segments.append((f"@{user_mentions[user_id]}", False))
		else:
			segments.append((match.group(0), True))

		current_pos = match.end()

	# Add remaining text
	if current_pos < len(content):
		segments.append((content[current_pos:], True))

	# Remove empty segments and strip Discord emojis from mockable segments
	processed_segments = []
	for text, should_mock in segments:
		if text:
			if should_mock:
				# Strip Discord emojis from mockable text
				text = re.sub(r'<a?:[a-zA-Z0-9_]+:\d+>', '', text)
				# Strip Unicode emojis
				text = text.encode('ascii', 'ignore').decode()
			if text.strip():  # Only add non-empty segments
				processed_segments.append((text, should_mock))

	return processed_segments

def _convert_to_mock_case(text: str) -> str:

	# Remove markdown formatting (##, **, __, etc.)
	clean_text = discord.utils.remove_markdown(text)
	# Convert to mocking case
	return ''.join(c.upper() if i % 2 else c.lower() for i, c in enumerate(clean_text))

def _fit_text_to_width(draw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:

	if draw.textlength(text, font=font) <= max_width:
		return text

	left, right = 0, len(text)
	while left < right:
		mid = (left + right + 1) // 2
		test_text = text[:mid] + "..."
		if draw.textlength(test_text, font=font) <= max_width:
			left = mid
		else:
			right = mid - 1

	return text[:left] + "..."

def _create_mock_image(segments: list) -> str:

	# Process each segment according to whether it should be mocked
	processed_text = ''
	for text, should_mock in segments:
		if should_mock:
			processed_text += _convert_to_mock_case(text)
		else:
			processed_text += text

	# Open the base image
	base_image = Image.open(_get_asset_path('mock.jpg'))

	# Create a drawing object
	draw = ImageDraw.Draw(base_image)

	# Load the font
	font = ImageFont.truetype(_get_asset_path('Impacted.ttf'), 36)

	# Get image dimensions
	img_w, img_h = base_image.size

	# Calculate maximum width for text (90% of image width)
	max_text_width = int(img_w * 0.9)

	# Fit text to width
	fitted_text = _fit_text_to_width(draw, processed_text, font, max_text_width)

	# Get text dimensions
	text_bbox = draw.textbbox((0, 0), fitted_text, font=font)
	text_w = text_bbox[2] - text_bbox[0]
	text_h = text_bbox[3] - text_bbox[1]

	# Calculate text position (centered)
	x = (img_w - text_w) // 2
	y = img_h - text_h - 20  # 20 pixels from bottom

	# Add text to image
	draw.text((x, y), fitted_text, font=font, fill='white')

	# Save the image
	output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'temp_mock.jpg')
	base_image.save(output_path)
	return output_path

def handle_mock(message: Message) -> discord.File:
	# if reply is None or reply.resolved is None:
	# 	return None
	if message.reference is None:
		return constants.REPLY_TO_MESSAGE

	reply = Message(message.reply.reference)

	# segments = process_text(reply.resolved, reply.resolved.content)
	segments = _process_text(reply.message_obj, reply.content)

	if not segments:
		return None

	image_path = _create_mock_image(segments)
	return discord.File(image_path)
