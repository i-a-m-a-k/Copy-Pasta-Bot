import io
import os
import re
from PIL import Image, ImageDraw, ImageFont
import discord
from typing import Optional
import constants

# --- Precompiled Regex Patterns ---
MENTION_REGEX = re.compile(r'<@!?(\d+)>')
CUSTOM_EMOJI_REGEX = re.compile(r'<a?:[a-zA-Z0-9_]+:\d+>')

# --- In-Memory Asset Caches ---
_BASE_IMAGE_CACHE: Optional[Image.Image] = None
_FONT_CACHE: Optional[ImageFont.FreeTypeFont] = None

def get_asset_path(filename: str) -> str:
    return os.path.join(constants.ASSETS_DIR, filename)

def get_base_mock_image() -> Image.Image:
    """Returns a fast in-memory copy of the pre-loaded mock.jpg base template."""
    global _BASE_IMAGE_CACHE
    if _BASE_IMAGE_CACHE is None:
        _BASE_IMAGE_CACHE = Image.open(get_asset_path('mock.jpg')).convert('RGB')
    return _BASE_IMAGE_CACHE.copy()

def get_mock_font() -> ImageFont.FreeTypeFont:
    """Returns the cached TrueType font object, avoiding disk parsing on each request."""
    global _FONT_CACHE
    if _FONT_CACHE is None:
        _FONT_CACHE = ImageFont.truetype(get_asset_path('Impacted.ttf'), 36)
    return _FONT_CACHE

def process_text(message: discord.Message, content: str) -> list[tuple[str, bool]]:
    # Create a mapping of user IDs to display names
    user_mentions = {
        str(user.id): user.display_name
        for user in message.mentions
    }
    
    segments = []
    current_pos = 0
    
    # Find all user mentions in the text using precompiled regex
    for match in MENTION_REGEX.finditer(content):
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
                text = CUSTOM_EMOJI_REGEX.sub('', text)
                text = text.encode('ascii', 'ignore').decode()
            if text.strip():
                processed_segments.append((text, should_mock))
    
    return processed_segments

def convert_to_mock_case(text: str) -> str:
    clean_text = discord.utils.remove_markdown(text)
    return ''.join(c.upper() if i % 2 else c.lower() for i, c in enumerate(clean_text))

def fit_text_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
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

def create_mock_image(segments: list[tuple[str, bool]]) -> io.BytesIO:
    processed_text = ''.join(
        convert_to_mock_case(text) if should_mock else text
        for text, should_mock in segments
    )
    
    # Clone pre-cached in-memory base image and retrieve cached TrueType font
    base_image = get_base_mock_image()
    font = get_mock_font()
    draw = ImageDraw.Draw(base_image)
    
    img_w, img_h = base_image.size
    max_text_width = int(img_w * 0.9)
    
    # Fit text to width using binary search
    fitted_text = fit_text_to_width(draw, processed_text, font, max_text_width)
    
    # Measure text dimensions
    text_bbox = draw.textbbox((0, 0), fitted_text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    
    x = (img_w - text_w) // 2
    y = img_h - text_h - 20
    
    draw.text((x, y), fitted_text, font=font, fill='white')
    
    buffer = io.BytesIO()
    base_image.save(buffer, format='JPEG', quality=90)
    buffer.seek(0)
    return buffer

def handle_mock_command(reply: discord.MessageReference) -> Optional[discord.File]:
    if reply is None or reply.resolved is None:
        return None
    
    segments = process_text(reply.resolved, reply.resolved.content)
    if not segments:
        return None
        
    buffer = create_mock_image(segments)
    return discord.File(buffer, filename='mock.jpg')
