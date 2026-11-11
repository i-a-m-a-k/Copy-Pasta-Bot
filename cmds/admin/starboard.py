import os
import sys
import json
from typing import Optional, Union
import discord
from core.config import is_admin
from ui.embeds import success_embed, error_embed, warning_embed, info_embed

STARBOARD_FILE = 'db/starboard.json'
STARBOARD_POSTS_FILE = 'db/starboard_posts.json'

# In-memory starboard config:
# { "guild_id_str": [ {"name": str, "channel_id": int, "emoji": str, "threshold": int}, ... ] }
starboard_config: dict[str, list[dict]] = {}

# Track starboard posts for live editing:
# { "guild_id_str": { "starboard_name": { original_message_id: starboard_message_id } } }
_posted_messages: dict[str, dict[str, dict[int, int]]] = {}

DEFAULT_EMOJI = '⭐'
DEFAULT_THRESHOLD = 3
MAX_STARBOARDS_PER_GUILD = 10

def load_starboard_config() -> dict:
	"""Loads starboard config from the JSON file."""
	if os.path.exists(STARBOARD_FILE):
		try:
			with open(STARBOARD_FILE, 'r') as f:
				data = json.load(f)
				# Migrate old single-config format to list format
				for gid, val in data.items():
					if isinstance(val, dict):
						val['name'] = 'default'
						data[gid] = [val]
				return data
		except (json.JSONDecodeError, FileNotFoundError):
			print("Could not read starboard.json, starting with empty dict.", file=sys.stderr)
			return {}
	return {}

def save_starboard_config():
	"""Saves the current starboard config to the JSON file."""
	try:
		os.makedirs(os.path.dirname(STARBOARD_FILE), exist_ok=True)
		with open(STARBOARD_FILE, 'w') as f:
			json.dump(starboard_config, f, indent=4)
	except IOError as e:
		print(f"Error saving starboard config: {e}", file=sys.stderr)

def load_starboard_posts() -> dict:
	"""Loads persisted starboard post mappings from JSON.
	Converts string keys back to int for message IDs."""
	if os.path.exists(STARBOARD_POSTS_FILE):
		try:
			with open(STARBOARD_POSTS_FILE, 'r') as f:
				data = json.load(f)
				# Convert string keys back to int
				result: dict[str, dict[str, dict[int, int]]] = {}
				for gid, boards in data.items():
					result[gid] = {}
					for board_name, mapping in boards.items():
						result[gid][board_name] = {int(k): v for k, v in mapping.items()}
				return result
		except (json.JSONDecodeError, FileNotFoundError, ValueError):
			print("Could not read starboard_posts.json, starting fresh.", file=sys.stderr)
			return {}
	return {}

def save_starboard_posts():
	"""Persists starboard post mappings to JSON."""
	try:
		os.makedirs(os.path.dirname(STARBOARD_POSTS_FILE), exist_ok=True)
		# Convert int keys to str for JSON serialization
		data: dict[str, dict[str, dict[str, int]]] = {}
		for gid, boards in _posted_messages.items():
			data[gid] = {}
			for board_name, mapping in boards.items():
				data[gid][board_name] = {str(k): v for k, v in mapping.items()}
		with open(STARBOARD_POSTS_FILE, 'w') as f:
			json.dump(data, f, indent=4)
	except IOError as e:
		print(f"Error saving starboard posts: {e}", file=sys.stderr)

def get_guild_starboards(guild_id: int) -> list[dict]:
	"""Returns all starboard configs for a guild (empty list if none)."""
	return starboard_config.get(str(guild_id), [])

def get_starboard_by_name(guild_id: int, name: str) -> Optional[dict]:
	"""Returns a specific starboard config by name, or None."""
	for sb in get_guild_starboards(guild_id):
		if sb['name'] == name:
			return sb
	return None

def get_starboard_by_emoji(guild_id: int, emoji: str) -> list[dict]:
	"""Returns all starboards in a guild that use the given emoji."""
	return [sb for sb in get_guild_starboards(guild_id) if sb['emoji'] == emoji]

def get_posted_entry(guild_id: int, board_name: str, message_id: int) -> Optional[int]:
	"""Returns the starboard message ID for a posted entry, or None if not posted."""
	gid = str(guild_id)
	return _posted_messages.get(gid, {}).get(board_name, {}).get(message_id)

def is_already_posted(guild_id: int, board_name: str, message_id: int) -> bool:
	"""Check if a message has already been posted to a specific starboard."""
	return get_posted_entry(guild_id, board_name, message_id) is not None

def mark_posted(guild_id: int, board_name: str, message_id: int, starboard_message_id: int):
	"""Record a starboard post mapping original message -> starboard message."""
	gid = str(guild_id)
	if gid not in _posted_messages:
		_posted_messages[gid] = {}
	if board_name not in _posted_messages[gid]:
		_posted_messages[gid][board_name] = {}
	_posted_messages[gid][board_name][message_id] = starboard_message_id
	save_starboard_posts()

def unmark_posted(guild_id: int, board_name: str, message_id: int):
	"""Remove a starboard post mapping (e.g. after deleting from starboard)."""
	gid = str(guild_id)
	if gid in _posted_messages and board_name in _posted_messages[gid]:
		_posted_messages[gid][board_name].pop(message_id, None)
		save_starboard_posts()

def _has_mod_perms(member: discord.Member) -> bool:
	"""Check if a member has moderator-level permissions in the guild."""
	perms = member.guild_permissions
	return perms.manage_guild or perms.administrator or perms.manage_messages

def _extract_channel_id(text: str) -> Optional[int]:
	"""Extract channel ID from a mention (<#123>) or raw ID string."""
	import re
	match = re.match(r'^<#(\d+)>$', text.strip())
	if match:
		return int(match.group(1))
	if text.strip().isdigit():
		return int(text.strip())
	return None

def _extract_emoji(text: str) -> Optional[str]:
	"""Extract an emoji from user input (Unicode or custom Discord emoji)."""
	import re
	text = text.strip()
	match = re.match(r'^<(a?):(\w+):(\d+)>$', text)
	if match:
		return text
	if len(text) <= 8 and not text.startswith('<'):
		return text
	return None

def _find_sb_index(guild_id: str, name: str) -> int:
	"""Find index of a starboard by name in the guild's list, or -1."""
	for i, sb in enumerate(starboard_config.get(guild_id, [])):
		if sb['name'] == name:
			return i
	return -1

async def handle_starboard(
	user: discord.User,
	args: list[str],
	message: discord.Message
) -> discord.Embed:
	"""
	Configure starboards for the current server.
	Usage:
	  ;;starboard                                          - List all starboards
	  ;;starboard add <name> #channel [emoji] [threshold]  - Add a starboard
	  ;;starboard remove <name>                            - Remove a starboard
	  ;;starboard edit <name> emoji <emoji>                - Change emoji
	  ;;starboard edit <name> threshold <n>                - Change threshold
	  ;;starboard edit <name> channel #channel             - Change channel
	"""
	if not message.guild:
		return error_embed("This command can only be used in a server.")

	member = message.guild.get_member(user.id)
	has_server_perms = member and _has_mod_perms(member)
	if not is_admin(user.id) and not has_server_perms:
		return error_embed("You don't have permission to use this command.")

	guild_id = str(message.guild.id)

	# --- No args: list all starboards ---
	if len(args) == 1:
		boards = get_guild_starboards(message.guild.id)
		if not boards:
			return info_embed(
				"No starboards configured for this server.\n"
				"Use `;;starboard add <name> #channel` to create one.",
				title="⭐ Starboard"
			)
		lines = []
		for sb in boards:
			channel = message.guild.get_channel(sb['channel_id'])
			ch_mention = f"<#{sb['channel_id']}>" if channel else f"Unknown ({sb['channel_id']})"
			lines.append(
				f"• **`{sb['name']}`** — {sb['emoji']} ×{sb['threshold']} → {ch_mention}"
			)
		return info_embed("\n".join(lines), title=f"⭐ Starboards ({len(boards)})")

	subcommand = args[1].lower()

	# --- Add: ;;starboard add <name> #channel [emoji] [threshold] ---
	if subcommand == 'add':
		if len(args) < 4:
			return error_embed(
				"Usage: `;;starboard add <name> #channel [emoji] [threshold]`\n"
				"Example: `;;starboard add hall-of-fame #hall-of-fame ⭐ 3`"
			)

		name = args[2].lower()
		if not name.isalnum() and '-' not in name and '_' not in name:
			return error_embed("Starboard name must be alphanumeric (hyphens and underscores allowed).")

		if get_starboard_by_name(message.guild.id, name):
			return error_embed(f"A starboard named `{name}` already exists.")

		boards = starboard_config.get(guild_id, [])
		if len(boards) >= MAX_STARBOARDS_PER_GUILD:
			return error_embed(f"Maximum of {MAX_STARBOARDS_PER_GUILD} starboards per server reached.")

		channel_id = _extract_channel_id(args[3])
		if channel_id is None:
			return error_embed("Please provide a valid channel mention (e.g. `#channel`) or channel ID.")

		channel = message.guild.get_channel(channel_id)
		if channel is None:
			return error_embed(f"Could not find channel <#{channel_id}> in this server.")

		emoji = DEFAULT_EMOJI
		threshold = DEFAULT_THRESHOLD

		if len(args) >= 5:
			parsed_emoji = _extract_emoji(args[4])
			if parsed_emoji is not None:
				emoji = parsed_emoji
			elif args[4].isdigit():
				threshold = max(1, int(args[4]))
			else:
				return error_embed(f"Invalid emoji: `{args[4]}`.")

		if len(args) >= 6 and args[5].isdigit():
			threshold = max(1, int(args[5]))

		new_board = {
			'name': name,
			'channel_id': channel_id,
			'emoji': emoji,
			'threshold': threshold,
		}
		if guild_id not in starboard_config:
			starboard_config[guild_id] = []
		starboard_config[guild_id].append(new_board)
		save_starboard_config()

		return success_embed(
			f"Starboard **`{name}`** created! Messages with **{threshold}** {emoji} "
			f"reaction(s) will be posted to <#{channel_id}>.",
			title="⭐ Starboard Added"
		)

	# --- Remove: ;;starboard remove <name> ---
	elif subcommand in ('remove', 'delete', 'rm'):
		if len(args) < 3:
			return error_embed("Usage: `;;starboard remove <name>`")

		name = args[2].lower()
		idx = _find_sb_index(guild_id, name)
		if idx == -1:
			return error_embed(f"No starboard named `{name}` found.")

		removed = starboard_config[guild_id].pop(idx)
		if not starboard_config[guild_id]:
			del starboard_config[guild_id]
		save_starboard_config()

		# Clear posted tracking for this board
		if guild_id in _posted_messages:
			_posted_messages[guild_id].pop(name, None)

		return success_embed(f"Starboard **`{name}`** has been removed.", title="⭐ Starboard Removed")

	# --- Edit: ;;starboard edit <name> <field> <value> ---
	elif subcommand == 'edit':
		if len(args) < 5:
			return error_embed(
				"Usage: `;;starboard edit <name> <field> <value>`\n"
				"Fields: `emoji`, `threshold`, `channel`\n"
				"Example: `;;starboard edit hall-of-fame emoji 🔥`"
			)

		name = args[2].lower()
		idx = _find_sb_index(guild_id, name)
		if idx == -1:
			return error_embed(f"No starboard named `{name}` found.")

		field = args[3].lower()
		value = args[4]

		if field == 'emoji':
			parsed_emoji = _extract_emoji(value)
			if parsed_emoji is None:
				return error_embed(f"Invalid emoji: `{value}`.")
			starboard_config[guild_id][idx]['emoji'] = parsed_emoji
			# Clear tracking so messages re-qualify with new emoji
			if guild_id in _posted_messages:
				_posted_messages[guild_id].pop(name, None)
			save_starboard_config()
			return success_embed(f"Starboard **`{name}`** emoji changed to {parsed_emoji}", title="⭐ Updated")

		elif field == 'threshold':
			if not value.isdigit():
				return error_embed("Threshold must be a positive number.")
			starboard_config[guild_id][idx]['threshold'] = max(1, int(value))
			if guild_id in _posted_messages:
				_posted_messages[guild_id].pop(name, None)
			save_starboard_config()
			return success_embed(f"Starboard **`{name}`** threshold changed to **{value}**", title="⭐ Updated")

		elif field == 'channel':
			channel_id = _extract_channel_id(value)
			if channel_id is None:
				return error_embed("Please provide a valid channel mention or ID.")
			channel = message.guild.get_channel(channel_id)
			if channel is None:
				return error_embed(f"Could not find channel <#{channel_id}> in this server.")
			starboard_config[guild_id][idx]['channel_id'] = channel_id
			save_starboard_config()
			return success_embed(f"Starboard **`{name}`** channel changed to <#{channel_id}>", title="⭐ Updated")

		else:
			return error_embed(f"Unknown field `{field}`. Valid fields: `emoji`, `threshold`, `channel`")

	else:
		return info_embed(
			"**Usage:**\n"
			"• `;;starboard` — List all starboards\n"
			"• `;;starboard add <name> #channel [emoji] [n]` — Add a starboard\n"
			"• `;;starboard remove <name>` — Remove a starboard\n"
			"• `;;starboard edit <name> emoji <emoji>` — Change emoji\n"
			"• `;;starboard edit <name> threshold <n>` — Change threshold\n"
			"• `;;starboard edit <name> channel #channel` — Change channel",
			title="⭐ Starboard Help"
		)
