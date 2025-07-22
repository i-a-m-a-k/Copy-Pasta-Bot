import random
import re
import nltk
import constants
from Message import Message

nltk.download('punkt')
nltk.download('averaged_perceptron_tagger_eng')

def _get_zalgo_chars():
	"""Returns lists of combining characters for above, middle, and below effects."""
	# Above combining characters (0x300-0x36F)
	above = [chr(x) for x in range(0x300, 0x36F)]
	# Middle combining characters (0x483-0x487)
	middle = [chr(x) for x in range(0x483, 0x487)]
	# Below combining characters (0x488-0x489)
	below = [chr(x) for x in range(0x488, 0x489)]

	return above, middle, below

def _add_zalgo_to_char(char:str, intensity:int=1) -> str:
	"""Add zalgo effects to a single character."""
	if char.strip() == '':
		return char

	above, middle, below = _get_zalgo_chars()
	zalgo_chars = []
	max_chars = max(1, intensity)  # Ensure at least 1 combining character if intensity > 0

	# Add above characters
	for _ in range(random.randint(0, max_chars - 1)):
		if len(zalgo_chars) < max_chars:
			zalgo_chars.append(random.choice(above))

	# Add middle characters occasionally
	if len(zalgo_chars) < max_chars and random.random() < 0.5:
		zalgo_chars.append(random.choice(middle))

	# Add below characters even less frequently
	if len(zalgo_chars) < max_chars and random.random() < 0.3:
		zalgo_chars.append(random.choice(below))

	return char + ''.join(zalgo_chars)

def _zalgo(text:str, intensity:int=2) -> str:
	# Dynamically adjust intensity based on input length
	adjusted_intensity = max(1, intensity - len(text) // 50)

	# Apply Zalgo effect to each character selectively
	zalgo_text = ''.join(
		_add_zalgo_to_char(c, adjusted_intensity) if random.random() < 0.7 else c
		for c in text
	)
	return zalgo_text

def _clap(text: str) -> str:
	# Split keeping whitespace to preserve formatting
	parts = text.split(' ')
	# Filter out empty strings but keep whitespace for formatting
	parts = [part if part.strip() else ' ' for part in parts]
	# Join non-empty parts with clap emoji
	return ' 👏 '.join(p for p in parts if p.strip())

def _stretch(text:str) -> str:
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

def _forbesify(text:str) -> str:
	words = text.split()
	tagged = nltk.pos_tag(words)
	result_words = []

	for word, tag in tagged:
		if tag in ['VB', 'VBD', 'VBG', 'VBN']:
			result_words.extend(['accidentally', word])
		else:
			result_words.append(word)

	return ' '.join(result_words)

def _owo(text:str) -> str:
	FACES = ['(・`ω´・)', ';;w;;', 'owo', 'UwU', '>w<', '^w^', r'\(^o\) (/o^)/',
			 '( ^ _ ^)∠☆', '(ô_ô)', '~:o', ';____;', '(*^*)', '(>_',
			 '(♥_♥)', '*(^O^)*', '((+_+))']

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

def _copypasta(text:str) -> str:
	EMOJIS = ["😂", "👌", "✌", "💞", "👍", "💯", "👀", "👓", "👏",
			  "👐", "🍕", "💥", "🍴", "💦", "🍑", "🍆", "😩", "😏",
			  "👉👌", "👅", "🚰"]

	user_tags = re.finditer(r'<@!?\d+>', text)
	tag_positions = [(m.start(), m.end(), m.group()) for m in user_tags]

	working_text = re.sub(r'<@!?\d+>', '', text)
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

def handle_text_transform(command_type:str, message:Message) -> str:
	if not message.reference:
		return constants.REPLY_TO_MESSAGE

	reply = Message(message.reference.resolved)
	if not reply:
		return constants.REPLY_TO_MESSAGE

	if not reply.content:
		return constants.WRONG_ARGS

	commands = {
		'clap': _clap,
		'copypasta': _copypasta,
		'forbesify': _forbesify,
		'owo': _owo,
		'stretch': _stretch,
		'zalgo': _zalgo
	}

	return commands[command_type](reply.content) or constants.WRONG_ARGS
