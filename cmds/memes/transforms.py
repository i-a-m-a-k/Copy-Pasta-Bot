import random
import re
from typing import Callable, Union
import discord
from ui.embeds import warning_embed

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
	EMOJIS = ["😂", "👌", "✌", "💞", "👍", "💯", "👀", "👓", "👏",
			  "👐", "🍕", "💥", "🍴", "💦", "🍑", "🍆", "😩", "😏",
			  "👉👌", "👅", "🚰"]
	text = reference.resolved.content
	user_tags = re.finditer(r'<@!?\d+>', text)
	tag_positions = [(m.start(), m.end(), m.group()) for m in user_tags]
	working_text = re.sub(r'<@!?\d+>', '', text)
	if not working_text.strip():
		return "Not enough text to copypasta (message is only mentions)."
	b_char = random.choice(working_text.lower())
	result = []
	for char in working_text:
		if char == " ":
			result.append(" " + random.choice(EMOJIS) + " ")
		elif char in EMOJIS:
			result.append(char + random.choice(EMOJIS))
		elif char.lower() == b_char:
			result.append("🅱️")
		else:
			result.append(char.upper() if random.getrandbits(1) else char.lower())

	final_result = [random.choice(EMOJIS) + " "]
	current_pos = 0
	result_text = ''.join(result)
	for start, end, tag in tag_positions:
		final_result.append(result_text[current_pos:start])
		final_result.append(tag + " ")
		current_pos = start
	final_result.append(result_text[current_pos:])
	final_result.append(" " + random.choice(EMOJIS))
	return ''.join(final_result)

# --- OwO ---
def handle_owo_command(reference: discord.MessageReference) -> str:
	if reference is None or not hasattr(reference, 'resolved') or not reference.resolved.content:
		return "You need to reply to a message to use this command."
	FACES = ['(・`ω´・)', ';;w;;', 'owo', 'UwU', '>w<', '^w^', r'\(^o\) (/o^)/',
			 '( ^ _ ^)∠☆', '(ô_ô)', '~:o', ';____;', '(*^*)', '(>_',
			 '(♥_♥)', '*(^O^)*', '((+_+))']
	text = reference.resolved.content
	user_tags = re.finditer(r'<@!?\d+>', text)
	tag_positions = [(m.start(), m.end(), m.group()) for m in user_tags]
	working_text = re.sub(r'<@!?\d+>', '', text)

	result = working_text
	result = re.sub(r'[rl]', "w", result)
	result = re.sub(r'[ｒｌ]', "ｗ", result)
	result = re.sub(r'[RL]', 'W', result)
	result = re.sub(r'[ＲＬ]', 'Ｗ', result)
	result = re.sub(r'n([aeiouａｅｉｏｕ])', r'ny\1', result)
	result = re.sub(r'ｎ([ａｅｉｏｕ])', r'ｎｙ\1', result)
	result = re.sub(r'N([aeiouAEIOU])', r'Ny\1', result)
	result = re.sub(r'Ｎ([ａｅｉｏｕＡＥＩＯＵ])', r'Ｎｙ\1', result)
	result = re.sub(r'\!+', ' ' + random.choice(FACES), result)
	result = re.sub(r'！+', ' ' + random.choice(FACES), result)
	result = result.replace("ove", "uv")
	result = result.replace("ｏｖｅ", "ｕｖ")

	final_result = []
	current_pos = 0
	for start, end, tag in tag_positions:
		final_result.append(result[current_pos:start])
		final_result.append(tag)
		current_pos = start
	final_result.append(result[current_pos:])
	final_result.append(' ' + random.choice(FACES))
	return ''.join(final_result)

# --- Stretch ---
def handle_stretch_command(reference: discord.MessageReference) -> str:
	if reference is None or not hasattr(reference, 'resolved') or not reference.resolved.content:
		return "You need to reply to a message to use this command."
	text = reference.resolved.content
	user_tags = re.finditer(r'<@!?\d+>', text)
	tag_positions = [(m.start(), m.end(), m.group()) for m in user_tags]
	working_text = re.sub(r'<@!?\d+>', '', text)
	count = random.randint(3, 10)
	result = re.sub(r'([aeiouAEIOUａｅｉｏｕＡＥＩＯＵ])', lambda m: m.group(1) * count, working_text)

	final_result = []
	current_pos = 0
	for start, end, tag in tag_positions:
		final_result.append(result[current_pos:start])
		final_result.append(tag)
		current_pos = start
	final_result.append(result[current_pos:])
	return ''.join(final_result)

# --- Vaporwave ---
def handle_vaporwave_command(reply: discord.MessageReference) -> str:
	if reply is None or not hasattr(reply, 'resolved') or not reply.resolved.content:
		return "You need to reply to a message to use this command."
	text = reply.resolved.content
	result = []
	for char in text:
		code = ord(char)
		if 0x21 <= code <= 0x7E:
			result.append(chr(code + 0xFEE0))
		elif char == ' ':
			result.append('\u3000')
		else:
			result.append(char)
	return ''.join(result)

# --- Emojify ---
def handle_emojify_command(reply: discord.MessageReference) -> str:
	if reply is None or not hasattr(reply, 'resolved') or not reply.resolved.content:
		return "You need to reply to a message to use this command."
	text = reply.resolved.content
	preserve_pattern = re.compile(r'(<@!?\d+>|<@&\d+>|<#\d+>|<a?:\w+:\d+>|https?://\S+)')
	parts = preserve_pattern.split(text)
	result_parts = []
	for part in parts:
		if preserve_pattern.match(part):
			result_parts.append(part)
		else:
			emojified = []
			for char in part.lower():
				if 'a' <= char <= 'z':
					emojified.append(chr(0x1F1E6 + ord(char) - ord('a')))
				elif '0' <= char <= '9':
					num_emojis = ['0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
					emojified.append(num_emojis[int(char)])
				elif char == ' ':
					emojified.append('   ')
				elif char == '?':
					emojified.append('❓')
				elif char == '!':
					emojified.append('❗')
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
