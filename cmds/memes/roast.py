import os
import random
import discord
import constants

def get_asset_path(filename: str) -> str:
	return os.path.join(constants.ASSETS_DIR, filename)

# Module-level cache — loaded once on first use
_ROASTS_CACHE = None

def load_roasts() -> list:
	"""Load roasts from the roasts.txt file (cached after first call)."""
	global _ROASTS_CACHE
	if _ROASTS_CACHE is not None:
		return _ROASTS_CACHE
	try:
		with open(get_asset_path('roasts.txt'), 'r', encoding='utf-8') as file:
			_ROASTS_CACHE = [line.strip() for line in file if line.strip()]
		return _ROASTS_CACHE
	except FileNotFoundError:
		print("Error: roasts.txt file not found in assets directory")
		return ["Error: Couldn't find roasts file. Contact the bot owner."]
	except Exception as e:
		print(f"Error loading roasts: {e}")
		return ["Error: Couldn't load roasts. Contact the bot owner."]

def get_random_roast(num: int = 1) -> list[str]:
	"""Get random roasts from the roasts file"""
	roasts = load_roasts()
	return random.sample(roasts, num)

def handle_roast(message: discord.Message, bot_user: discord.ClientUser) -> str:
	"""Handle the ;;roast command and return the response message"""
	no_mentions = False
	bot_mention = False

	if not message.mentions:
		target_users = [message.author]
		no_mentions = True
	elif bot_user in message.mentions:
		target_users = [message.author]
		bot_mention = True
	else:
		target_users = message.mentions

	roasts = get_random_roast(len(target_users))

	response = ''
	for i, user in enumerate(target_users):
		response += f'{user.mention} {discord.utils.escape_markdown(roasts[i])}\n'

	if no_mentions:
		response += '\nTry reading `;;help` twice next time'
	if bot_mention:
		response += '\nWhy would I roast myself?'

	return response.strip()
