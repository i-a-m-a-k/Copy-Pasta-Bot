import os
import random
import discord

def get_asset_path(filename: str) -> str:
	root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	return os.path.join(root_dir, 'assets', filename)

# Module-level cache — loaded once on first use
_ROASTS_CACHE = None

def load_roasts() -> list:
	"""Load roasts from the roasts.txt file (cached after first call)."""
	global _ROASTS_CACHE
	if _ROASTS_CACHE is not None:
		return _ROASTS_CACHE
	try:
		with open(get_asset_path('roasts.txt'), 'r', encoding='utf-8') as file:
			# Filter out empty lines
			_ROASTS_CACHE = [line.strip() for line in file if line.strip()]
		return _ROASTS_CACHE
	except FileNotFoundError:
		print("Error: roasts.txt file not found in assets directory")
		return ["Error: Couldn't find roasts file. Contact the bot owner."]
	except Exception as e:
		print(f"Error loading roasts: {e}")
		return ["Error: Couldn't load roasts. Contact the bot owner."]

def get_random_roast(num=1) -> str:
	"""Get a random roast from the roasts file"""
	roasts = load_roasts()
	return random.sample(roasts, num)

def handle_roast(message: discord.Message, bot_user: discord.ClientUser) -> str:
	"""Handle the ;;roast command and return the response message"""
	no_mentions = False
	bot_mention = False

	# Check if there's a user mention in the message
	if not message.mentions:
		target_users = [message.author]
		no_mentions = True

	elif bot_user in message.mentions:
		target_users = [message.author]
		bot_mention = True

	else:
		target_users = message.mentions

	# Get random roasts
	roasts = get_random_roast(len(target_users))

	# Format the response with the target user mention and the roast
	# Using discord.utils.escape_markdown to preserve '*' for censoring 
	response = ''
	for i, user in enumerate(target_users):
		response += f'{user.mention} {discord.utils.escape_markdown(roasts[i])}\n'

	if no_mentions:
		response += '\nTry reading `;;help` twice next time'
	if bot_mention:
		response += '\nWhy would I roast myself?'

	return response.strip()