import os
import sys
import json
import re
from typing import Optional, Union

import constants
import do_not_push

BLACKLIST_FILE = 'db/blacklist.json'
DISABLED_COMMANDS_FILE = 'db/disabled_commands.json'

# In-memory store: { "guild_id": ["command1", "command2"] }
disabled_commands = {}

def extract_user_id(mention_or_id: str) -> Optional[int]:
	"""Extracts integer user ID from a Discord mention (<@123> or <@!123>) or raw ID string."""
	if not mention_or_id:
		return None
	mention_or_id = str(mention_or_id).strip()
	match = re.match(r'^<@!?(\d+)>$', mention_or_id)
	if match:
		return int(match.group(1))
	if mention_or_id.isdigit():
		return int(mention_or_id)
	return None

def is_admin(user_id: Union[int, str]) -> bool:
	"""Checks if a user ID is listed as a bot admin in configuration."""
	try:
		return int(user_id) in do_not_push.ADMINS
	except (ValueError, TypeError):
		return False

def is_blacklisted(user_id: Union[int, str]) -> bool:
	"""Checks if a user ID is blacklisted from using the bot."""
	try:
		return int(user_id) in constants.BLACKLIST
	except (ValueError, TypeError):
		return False

def load_blacklist() -> list:
	"""Loads the blacklist from the JSON file."""
	if os.path.exists(BLACKLIST_FILE):
		try:
			with open(BLACKLIST_FILE, 'r') as f:
				return json.load(f)
		except (json.JSONDecodeError, FileNotFoundError):
			print("Could not read blacklist.json, starting with empty list.", file=sys.stderr)
			return []
	return []

def save_blacklist():
	"""Saves the current blacklist to the JSON file."""
	try:
		os.makedirs(os.path.dirname(BLACKLIST_FILE), exist_ok=True)
		with open(BLACKLIST_FILE, 'w') as f:
			json.dump(constants.BLACKLIST, f, indent=4)
	except IOError as e:
		print(f"Error saving blacklist: {e}", file=sys.stderr)

def load_disabled_commands() -> dict:
	"""Loads the disabled commands from the JSON file."""
	if os.path.exists(DISABLED_COMMANDS_FILE):
		try:
			with open(DISABLED_COMMANDS_FILE, 'r') as f:
				return json.load(f)
		except (json.JSONDecodeError, FileNotFoundError):
			print("Could not read disabled_commands.json, starting with empty dict.", file=sys.stderr)
			return {}
	return {}

def save_disabled_commands():
	"""Saves the current disabled commands to the JSON file."""
	try:
		os.makedirs(os.path.dirname(DISABLED_COMMANDS_FILE), exist_ok=True)
		with open(DISABLED_COMMANDS_FILE, 'w') as f:
			json.dump(disabled_commands, f, indent=4)
	except IOError as e:
		print(f"Error saving disabled commands: {e}", file=sys.stderr)

def is_command_disabled(guild_id: int, command: str) -> bool:
	"""Checks if a command is disabled for a specific guild."""
	return command in disabled_commands.get(str(guild_id), [])
