import os
import random
import discord
import constants
from Message import Message

def _get_asset_path(filename: str) -> str:
	root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	return os.path.join(root_dir, 'assets', filename)

def _load_roasts() -> list:
	"""Load roasts from the roasts.txt file"""
	try:
		with open(_get_asset_path(constants.ROASTS_NAME), 'r', encoding='utf-8') as file:
			# Filter out empty lines
			roasts = [line.strip() for line in file if line.strip()]
		return roasts
	except FileNotFoundError:
		print("Error: roasts.txt file not found in assets directory")
		return ["Error: Couldn't find roasts file. Contact the bot owner."]
	except Exception as e:
		print(f"Error loading roasts: {e}")
		return ["Error: Couldn't load roasts. Contact the bot owner."]

def _get_random_roast(num=1) -> str:
	"""Get a random roast from the roasts file"""
	roasts = _load_roasts()
	return random.sample(roasts, num)

def roast(message: discord.Message, bot_user: discord.ClientUser) -> str:
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
	roasts = _get_random_roast(len(target_users))

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

def add_roast(message: Message) -> str:
	if len(message.args) <= 1:
		return constants.WRONG_ARGS

	roast = message.content[12:].strip()
	roasts = _load_roasts()

	if len(roasts) > 0 and roasts[0][:6] == 'Error:':
		return constants.UNSUCCESSFUL

	if roast not in roasts:
		roasts.append(roast)

	try:
		with open(_get_asset_path(constants.ROASTS_NAME), 'w') as f:
			f.write('\n'.join(roasts))

		return constants.SUCCESSFUL
	except Exception as e:
		print('Exception in `add_roast`: ', e)
		return constants.UNSUCCESSFUL
