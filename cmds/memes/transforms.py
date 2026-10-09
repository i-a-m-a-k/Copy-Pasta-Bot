import random
import re
from typing import Callable, Union
import discord
from ui.embeds import warning_embed

# --- Precompiled Global Regex Patterns & Translation Tables ---
USER_TAG_REGEX = re.compile(r'<@!?\d+>')
VOWELS_REGEX = re.compile(r'([aeiouAEIOUａｅｉｏｕＡＥＩＯＵ])')
PRESERVE_PATTERN = re.compile(r'(<@!?\d+>|<@&\d+>|<#\d+>|<a?:\w+:\d+>|https?://\S+)')

# C-accelerated translation table for Vaporwave (fullwidth conversion)
VAPORWAVE_TRANS = str.maketrans({
	i: chr(i + 0xFEE0) for i in range(0x21, 0x7F)
} | {ord(' '): '\u3000'})

# Precompiled OwO substitutions
OWO_SUBSTITUTIONS = [
	(re.compile(r'[rl]'), 'w'),
	(re.compile(r'[ｒｌ]'), 'ｗ'),
	(re.compile(r'[RL]'), 'W'),
	(re.compile(r'[ＲＬ]'), 'Ｗ'),
	(re.compile(r'n([aeiouａｅｉｏｕ])'), r'ny\1'),
	(re.compile(r'ｎ([ａｅｉｏｕ])'), r'ｎｙ\1'),
	(re.compile(r'N([aeiouAEIOU])'), r'Ny\1'),
	(re.compile(r'Ｎ([ａｅｉｏｕＡＥＩＯＵ])'), r'Ｎｙ\1'),
	(re.compile(r'\!+'), ' !'),
	(re.compile(r'！+'), ' ！'),
]

OWO_FACES = [
	'(・`ω´・)', ';;w;;', 'owo', 'UwU', '>w<', '^w^', r'\\(^o\\) (/o^)/',
	'( ^ _ ^)∠☆', '(ô_ô)', '~:o', ';____;', '(*^*)', '(>_',
	'(♥_♥)', '*(^O^)*', '((+_+))'
]

COPYPASTA_EMOJIS = [
	"😂", "👌", "✌", "💞", "👍", "💯", "👀", "👓", "👏",
	"👐", "🍕", "💥", "🍴", "💦", "🍑", "🍆", "😩", "😏",
	"👉👌", "👅", "🚰"
]

NUM_EMOJIS = {
	'0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
	'5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣',
	'?': '❓', '!': '❗'
}

# --- Clap ---
def handle_clap_command(reply: discord.MessageReference) -> str:
	if not reply or not hasattr(reply, 'resolved') or not reply.resolved.content:
		return "Cannot clap an empty message or a message with only attachments."
	parts = reply.resolved.content.split(' ')
	parts = [part if part.strip() else ' ' for part in parts]
	return ' 👏 '.join(p for p in parts if p.strip())

# --- Zalgo ---
def _get_zalgo_chars():
	above = [chr(x) for x in range(0x300, 0x36F)]
	middle = [chr(x) for x in range(0x483, 0x487)]
	below = [chr(x) for x in range(0x488, 0x489)]
	return above, middle, below

def _add_zalgo_to_char(char: str, intensity: int = 1) -> str:
	if char.strip() == '':
		return char
	above, middle, below = _get_zalgo_chars()
	zalgo_chars = []
	max_chars = max(1, intensity)
	for _ in range(random.randint(0, max_chars - 1)):
		if len(zalgo_chars) < max_chars:
			zalgo_chars.append(random.choice(above))
	if len(zalgo_chars) < max_chars and random.random() < 0.5:
		zalgo_chars.append(random.choice(middle))
	if len(zalgo_chars) < max_chars and random.random() < 0.3:
		zalgo_chars.append(random.choice(below))
	return char + ''.join(zalgo_chars)

def handle_zalgo_command(reply: discord.MessageReference, intensity: int = 2) -> str:
	if not reply or not hasattr(reply, 'resolved') or not reply.resolved.content:
		return "Cannot apply zalgo to an empty message or a message with only attachments."
	text = reply.resolved.content.strip()
	adjusted_intensity = max(1, intensity - len(text) // 50)
	return ''.join(
		_add_zalgo_to_char(c, adjusted_intensity) if random.random() < 0.7 else c
		for c in text
	)

# --- Copypasta Emoji Text ---
def handle_copypasta_command(reference: discord.MessageReference) -> str:
	if reference is None or not hasattr(reference, 'resolved') or not reference.resolved.content:
		return "You need to reply to a message to use this command."
	text = reference.resolved.content
	user_tags = USER_TAG_REGEX.finditer(text)
	tag_positions = [(m.start(), m.end(), m.group()) for m in user_tags]
	working_text = USER_TAG_REGEX.sub('', text)
	if not working_text.strip():
		return "Not enough text to copypasta (message is only mentions)."
	b_char = random.choice(working_text.lower())
	result = []
	for char in working_text:
		if char == " ":
			result.append(" " + random.choice(COPYPASTA_EMOJIS) + " ")
		elif char in COPYPASTA_EMOJIS:
			result.append(char + random.choice(COPYPASTA_EMOJIS))
		elif char.lower() == b_char:
			result.append("🅱️")
		else:
			result.append(char.upper() if random.getrandbits(1) else char.lower())

	final_result = [random.choice(COPYPASTA_EMOJIS) + " "]
	current_pos = 0
	result_text = ''.join(result)
	for start, end, tag in tag_positions:
		final_result.append(result_text[current_pos:start])
		final_result.append(tag + " ")
		current_pos = start
	final_result.append(result_text[current_pos:])
	final_result.append(" " + random.choice(COPYPASTA_EMOJIS))
	return ''.join(final_result)

# --- OwO ---
def handle_owo_command(reference: discord.MessageReference) -> str:
	if reference is None or not hasattr(reference, 'resolved') or not reference.resolved.content:
		return "You need to reply to a message to use this command."
	text = reference.resolved.content
	user_tags = USER_TAG_REGEX.finditer(text)
	tag_positions = [(m.start(), m.end(), m.group()) for m in user_tags]
	working_text = USER_TAG_REGEX.sub('', text)

	result = working_text
	for pattern, replacement in OWO_SUBSTITUTIONS:
		if replacement in {' !', ' ！'}:
			result = pattern.sub(' ' + random.choice(OWO_FACES), result)
		else:
			result = pattern.sub(replacement, result)

	result = result.replace("ove", "uv").replace("ｏｖｅ", "ｕｖ")

	final_result = []
	current_pos = 0
	for start, end, tag in tag_positions:
		final_result.append(result[current_pos:start])
		final_result.append(tag)
		current_pos = start
	final_result.append(result[current_pos:])
	final_result.append(' ' + random.choice(OWO_FACES))
	return ''.join(final_result)

# --- Stretch ---
def handle_stretch_command(reference: discord.MessageReference) -> str:
	if reference is None or not hasattr(reference, 'resolved') or not reference.resolved.content:
		return "You need to reply to a message to use this command."
	text = reference.resolved.content
	user_tags = USER_TAG_REGEX.finditer(text)
	tag_positions = [(m.start(), m.end(), m.group()) for m in user_tags]
	working_text = USER_TAG_REGEX.sub('', text)
	count = random.randint(3, 10)
	result = VOWELS_REGEX.sub(lambda m: m.group(1) * count, working_text)

	final_result = []
	current_pos = 0
	for start, end, tag in tag_positions:
		final_result.append(result[current_pos:start])
		final_result.append(tag)
		current_pos = start
	final_result.append(result[current_pos:])
	return ''.join(final_result)

# --- Vaporwave (C-accelerated translation table) ---
def handle_vaporwave_command(reply: discord.MessageReference) -> str:
	if reply is None or not hasattr(reply, 'resolved') or not reply.resolved.content:
		return "You need to reply to a message to use this command."
	text = reply.resolved.content
	if not text:
		return "Message has no text content to vaporwave."
	return text.translate(VAPORWAVE_TRANS)

# --- Emojify ---
def handle_emojify_command(reply: discord.MessageReference) -> str:
	if reply is None or not hasattr(reply, 'resolved') or not reply.resolved.content:
		return "You need to reply to a message to use this command."
	text = reply.resolved.content
	parts = PRESERVE_PATTERN.split(text)
	result_parts = []
	for part in parts:
		if PRESERVE_PATTERN.match(part):
			result_parts.append(part)
		else:
			emojified = []
			for char in part.lower():
				if 'a' <= char <= 'z':
					emojified.append(chr(0x1F1E6 + ord(char) - ord('a')))
				elif char in NUM_EMOJIS:
					emojified.append(NUM_EMOJIS[char])
				elif char == ' ':
					emojified.append('   ')
				else:
					emojified.append(char)
			result_parts.append(' '.join(emojified))
	return ' '.join(result_parts)

# --- Dispatcher Factory ---
TRANSFORM_HANDLERS = {
	'clap': handle_clap_command,
	'zalgo': handle_zalgo_command,
	'copypasta': handle_copypasta_command,
	'owo': handle_owo_command,
	'stretch': handle_stretch_command,
	'vaporwave': handle_vaporwave_command,
	'emojify': handle_emojify_command
}

def create_transform_handler(command_type: str) -> Callable:
	"""Factory that creates a text transformer command handler."""
	handler_fn = TRANSFORM_HANDLERS[command_type]

	def handler(user: discord.User, args: list[str], reply: discord.MessageReference, message: discord.Message = None) -> Union[str, discord.Embed]:
		if reply is None or reply.resolved is None:
			return warning_embed("You need to reply to a message to use this command.")
		return handler_fn(reply)

	return handler
