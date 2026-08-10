import do_not_push
import constants
import re
import asyncio
from typing import Optional, Union, Callable
import discord
import os
from sqlitedict import SqliteDict
from cmds import *
import sys
from datetime import datetime, timedelta, timezone
import random
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
	try:
		return int(user_id) in do_not_push.ADMINS
	except (ValueError, TypeError):
		return False

def is_blacklisted(user_id: Union[int, str]) -> bool:
	try:
		return int(user_id) in constants.BLACKLIST
	except (ValueError, TypeError):
		return False

def _load_blacklist() -> list:
	"""Loads the blacklist from the JSON file."""
	if os.path.exists(BLACKLIST_FILE):
		try:
			with open(BLACKLIST_FILE, 'r') as f:
				return json.load(f)
		except (json.JSONDecodeError, FileNotFoundError):
			print("Could not read blacklist.json, starting with empty list.", file=sys.stderr)
			return []
	return []

def _save_blacklist():
	"""Saves the current blacklist to the JSON file."""
	try:
		with open(BLACKLIST_FILE, 'w') as f:
			json.dump(constants.BLACKLIST, f, indent=4)
	except IOError as e:
		print(f"Error saving blacklist: {e}", file=sys.stderr)

def _load_disabled_commands() -> dict:
	"""Loads the disabled commands from the JSON file."""
	if os.path.exists(DISABLED_COMMANDS_FILE):
		try:
			with open(DISABLED_COMMANDS_FILE, 'r') as f:
				return json.load(f)
		except (json.JSONDecodeError, FileNotFoundError):
			print("Could not read disabled_commands.json, starting with empty dict.", file=sys.stderr)
			return {}
	return {}

def _save_disabled_commands():
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

def success_embed(description: str, title: Optional[str] = None) -> discord.Embed:
	embed = discord.Embed(description=description, color=discord.Color.green())
	if title:
		embed.title = title
	return embed

def error_embed(description: str, title: Optional[str] = None) -> discord.Embed:
	embed = discord.Embed(description=description, color=discord.Color.red())
	if title:
		embed.title = title
	return embed

def warning_embed(description: str, title: Optional[str] = None) -> discord.Embed:
	embed = discord.Embed(description=description, color=discord.Color.gold())
	if title:
		embed.title = title
	return embed

def info_embed(description: str, title: Optional[str] = None) -> discord.Embed:
	embed = discord.Embed(description=description, color=discord.Color.blurple())
	if title:
		embed.title = title
	return embed

class SavedPaginationView(discord.ui.View):
	def __init__(self, invoking_user_id: int, target_user_id: int, keys: list[str], timeout: float = 180.0):
		super().__init__(timeout=timeout)
		self.invoking_user_id = invoking_user_id
		self.target_user_id = target_user_id
		self.keys = keys
		self.current_page = 0
		self.per_page = 10
		self.total_pages = max(1, (len(keys) + self.per_page - 1) // self.per_page)
		self.message = None
		self._update_buttons()

	def get_embed(self) -> discord.Embed:
		start_idx = self.current_page * self.per_page
		end_idx = start_idx + self.per_page
		page_keys = self.keys[start_idx:end_idx]

		embed = discord.Embed(
			title="Saved Keys",
			description=f"Saved messages for <@{self.target_user_id}>\n\n" + "\n".join([f"- `{k}`" for k in page_keys]),
			color=discord.Color.blurple()
		)
		embed.set_footer(text=f"Page {self.current_page + 1} of {self.total_pages} • Total: {len(self.keys)} key(s)")
		return embed

	def _update_buttons(self):
		self.first_button.disabled = (self.current_page == 0)
		self.prev_button.disabled = (self.current_page == 0)
		self.page_indicator.label = f"{self.current_page + 1}/{self.total_pages}"
		self.next_button.disabled = (self.current_page >= self.total_pages - 1)
		self.last_button.disabled = (self.current_page >= self.total_pages - 1)

	async def interaction_check(self, interaction: discord.Interaction) -> bool:
		if interaction.user.id != self.invoking_user_id and not is_admin(interaction.user.id):
			await interaction.response.send_message(
				"You cannot interact with these buttons because you did not invoke this command.",
				ephemeral=True
			)
			return False
		return True

	@discord.ui.button(label="⏮️", style=discord.ButtonStyle.secondary, custom_id="saved_first")
	async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		self.current_page = 0
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="◀️", style=discord.ButtonStyle.primary, custom_id="saved_prev")
	async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		if self.current_page > 0:
			self.current_page -= 1
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True, custom_id="saved_indicator")
	async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
		pass

	@discord.ui.button(label="▶️", style=discord.ButtonStyle.primary, custom_id="saved_next")
	async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		if self.current_page < self.total_pages - 1:
			self.current_page += 1
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary, custom_id="saved_last")
	async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		self.current_page = self.total_pages - 1
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	async def on_timeout(self):
		for child in self.children:
			child.disabled = True
		if self.message:
			try:
				await self.message.edit(view=self)
			except Exception:
				pass

class DatabaseManager:
	def __init__(self, db_name: str):
		self.db = SqliteDict(db_name, autocommit=True)

	def _get_user_entry(self, user: Union[int, str, discord.User, discord.Member]) -> tuple[Union[int, str], dict]:
		if hasattr(user, 'id'):
			user = user.id

		if user in self.db:
			return user, self.db[user]

		alt_user = str(user) if isinstance(user, int) else (int(user) if str(user).isdigit() else user)
		if alt_user in self.db:
			return alt_user, self.db[alt_user]

		return user, {}

	def store_text(self, user: Union[int, str, discord.User, discord.Member], key: str, value: str, overwrite=False) -> str:
		key_user, user_db = self._get_user_entry(user)
		if key in user_db and not overwrite:
			return constants.KEY_EXISTS_ADD
		user_db[key] = value
		self.db[key_user] = user_db
		return constants.SUCCESSFUL

	def retrieve_text(self, user: Union[int, str, discord.User, discord.Member], key: str) -> Optional[str]:
		_, user_db = self._get_user_entry(user)
		return user_db.get(key)

	def get_user_keys(self, user: Union[int, str, discord.User, discord.Member]) -> list:
		_, user_db = self._get_user_entry(user)
		return list(user_db.keys())

	def close(self):
		self.db.close()

	def delete_key(self, user: Union[int, str, discord.User, discord.Member], key: str) -> bool:
		key_user, user_db = self._get_user_entry(user)
		if key in user_db:
			del user_db[key]
			self.db[key_user] = user_db
			return True
		return False

	def find_all_keys_by_value(self, value: str) -> list:
		"""Reverse-lookup: find all (user_id, key) pairs that store this value.
		Returns a list of all matches found.
		Comparison is whitespace-normalized to handle trailing spaces
		from attachment/sticker formatting."""
		results = []
		normalized_value = value.strip()
		for user_id in self.db.keys():
			user_db = self.db.get(user_id, {})
			for key, stored_value in user_db.items():
				if stored_value.strip() == normalized_value:
					results.append((user_id, key))
		return results

	def copy_database(self, new_db:SqliteDict):
		for key in self.db.keys():
			new_db[key] = self.db[key]

		return new_db

class CommandHandler:
	def __init__(self, db_manager: DatabaseManager, get_bot: Callable):
		self.db = db_manager
		self.commands = {
			'add': lambda u, a, r, m: self._handle_add(u, a, r, m),
			'add_o': lambda u, a, r, m: self._handle_add(u, a, r, m, True),
			'saved': lambda u, a, r, m: self._handle_saved(u, a, m),
			'delete': lambda u, a, r, m: self._handle_delete(u, a, r),
			'delete_me': lambda u, a, r, m: self._handle_delete_me(u, a, r),
			'rename': lambda u, a, r, m: self._handle_rename(u, a, False),
			'rename_o': lambda u, a, r, m: self._handle_rename(u, a, True),
			'mock': lambda u, a, r, m: self._handle_mock(u, a, r),
			'steal': lambda u, a, r, m: self._handle_steal(u, a, r),
			'help': lambda u, a, r, m: self._handle_help(a),
			'blacklist_add': lambda u, a, r, m: self._handle_blacklist_add(u, a, r),
			'blacklist_remove': lambda u, a, r, m: self._handle_blacklist_remove(u, a, r),
			'clap': self._handle_text_transform('clap'),
			'zalgo': self._handle_text_transform('zalgo'),
			'copypasta': self._handle_text_transform('copypasta'),
			'owo': self._handle_text_transform('owo'),
			'stretch': self._handle_text_transform('stretch'),
			'vaporwave': self._handle_text_transform('vaporwave'),
			'emojify': self._handle_text_transform('emojify'),
			'roast': lambda u, a, r, m: self._handle_roast(u, a, r, m),
			'flirt': lambda u, a, r, m: self._handle_flirt(u, a, r, m),
			'random': lambda u, a, r, m: self._handle_random(u, a),
			'grandom': lambda u, a, r, m: self._handle_grandom(u, a),
			'search': lambda u, a, r, m: self._handle_search(u, a),
			's': lambda u, a, r, m: regexc.handle_regex(a, r),
			'deepfry': lambda u, a, r, m: self._handle_deepfry(u, a, r, m),
			'dream': lambda u, a, r, m: self._handle_dream(u, a, r),
			'disable': lambda u, a, r, m: self._handle_disable(u, a, m),
			'enable': lambda u, a, r, m: self._handle_enable(u, a, m),
			'delkey': lambda u, a, r, m: self._handle_delkey(u, a, r, m),
			'gsearch': lambda u, a, r, m: self._handle_gsearch(u, a)
		}
		self.get_bot = get_bot

	def _handle_add(self, user: discord.User, args: list, reply, message, overwrite=False) -> discord.Embed:
		if len(args) == 1:
			return error_embed("Usage: `;;add <key> <value>` or `;;add <key>` (replying to a message / adding an attachment)")

		key_name = args[1]

		if len(args) == 2:
			if reply is None and len(message.attachments) == 0:
				return error_embed("Usage: `;;add <key> <value>` or `;;add <key>` (replying to a message / adding an attachment)")

			if reply:
				original_message = reply.resolved.content.strip() or ''
				original_message += self._get_attachments_text(reply.resolved)
			else:
				original_message = ''
			original_message += self._get_attachments_text(message)

			if not original_message:
				return error_embed(constants.EMPTY_MESSAGE)

			status = self.db.store_text(user.id, key_name, original_message, overwrite)
		else:
			status = self.db.store_text(user.id, key_name, ' '.join(args[2:]), overwrite)

		if status == constants.SUCCESSFUL:
			action = "overwritten" if overwrite else "saved"
			return success_embed(f"Key `{key_name}` has been {action} successfully!")
		elif status == constants.KEY_EXISTS_ADD:
			return warning_embed(f"Key `{key_name}` already exists. Use `;;add_o` to overwrite.")
		return error_embed(status)

	def _get_attachments_text(self, message: discord.Message) -> str:
		text = ''
		for i, attachment in enumerate(message.attachments):
			text += f'[Attachment {i}]({attachment.url}) '
		for sticker in message.stickers:
			text += f'[{sticker.name}]({sticker.url}) '
		return text

	def _handle_saved(self, user: discord.User, args: list, message=None) -> Union[discord.Embed, dict]:
		if len(args) == 2:
			target_id = extract_user_id(args[1])
			if target_id is not None:
				if not is_admin(user.id):
					return error_embed("You don't have permission to view another user's keys.")
				find_keys_for = target_id
			else:
				find_keys_for = user.id
		else:
			find_keys_for = user.id

		keys = sorted(self.db.get_user_keys(find_keys_for))
		if len(keys) == 0:
			msg = "You have not saved any keys yet." if find_keys_for == user.id else f"<@{find_keys_for}> has not saved any keys yet."
			return info_embed(msg)

		view = SavedPaginationView(invoking_user_id=user.id, target_user_id=find_keys_for, keys=keys)
		return {
			"type": "saved_pagination",
			"embed": view.get_embed(),
			"view": view
		}

	def _handle_text_transform(self, command_type: str) -> Callable:
		handlers = {
			'clap': clap.handle_clap_command,
			'zalgo': zalgo.handle_zalgo_command,
			'copypasta': copypasta.handle_copypasta_command,
			'owo': owo.handle_owo_command,
			'stretch': stretch.handle_stretch_command,
			'vaporwave': vaporwave.handle_vaporwave_command,
			'emojify': emojify.handle_emojify_command
		}

		def handler(user: discord.User, args: list, reply, message=None) -> Union[str, discord.Embed]:
			if reply is None:
				return warning_embed("You need to reply to a message to use this command.")
			return handlers[command_type](reply)

		return handler

	def _handle_delete(self, user: discord.User, args: list, reply) -> discord.Embed:
		if len(args) == 1:
			return error_embed("Usage: `;;delete <key>`")
		key_name = args[1]
		if self.db.delete_key(user.id, key_name):
			return success_embed(f"Deleted key `{key_name}` from your saved keys.")
		return error_embed(f"Key `{key_name}` does not exist.")

	def _handle_delete_me(self, user: discord.User, args: list, reply) -> discord.Embed:
		if delete_me.delete_me(self.db.db, user.id):
			return success_embed("All your saved keys have been deleted.")
		return info_embed("You don't have any saved keys to delete.")

	def _handle_rename(self, user: discord.User, args: list, overwrite: bool) -> discord.Embed:
		if len(args) != 3:
			cmd_name = "rename_o" if overwrite else "rename"
			return error_embed(f"Usage: `;;{cmd_name} <original_key> <new_key>`")
		old_key, new_key = args[1], args[2]
		status = rename_key.rename_key(self.db.db, user.id, old_key, new_key, overwrite)
		match status:
			case 0:
				return success_embed(f"Renamed key `{old_key}` to `{new_key}`.")
			case -1:
				return info_embed("You have not saved any keys yet.")
			case -2:
				return error_embed(f"Key `{old_key}` does not exist.")
			case -3:
				return warning_embed(f"Key `{new_key}` already exists. Use `;;rename_o` to overwrite.")
			case _:
				return error_embed("Something went wrong while renaming the key.")

	def _handle_mock(self, user: discord.User, args: list, reply) -> Union[discord.Embed, discord.File]:
		if reply is None:
			return warning_embed("You need to reply to a message to use this command.")
		return mock.handle_mock_command(reply)
	
	def _handle_flirt(self, user: discord.User, args: list, reply, message) -> Union[dict, discord.Embed]:
		if len(message.mentions) == 0:
			return warning_embed("You need to mention someone to flirt with! Try `;;flirt @username`")
		flirt_text = flirt.handle_flirt_command(message)

		return {
			"type": "puppet",
			"content": flirt_text,
			"author": user,
			"target_channel": message.channel
		}
	
	def _handle_roast(self, user: discord.User, args: list, reply, message) -> dict:
		roast_text = roast.handle_roast(message, self.get_bot())

		return {
			"type": "puppet",
			"content": roast_text,
			"author": user,
			"target_channel": message.channel
		}

	async def _handle_deepfry(self, user: discord.User, args: list, reply, message=None) -> Union[discord.Embed, discord.File]:
		if reply is None and (message is None or not message.attachments):
			return warning_embed("You need to reply to a message with an image or attach one to use this command.")
		return await deepfry.handle_deepfry_command(reply, message)

	async def _handle_dream(self, user: discord.User, args: list, reply) -> Union[str, discord.File, discord.Embed, None]:
		return await dream.handle_dream_command(user, args, message=reply)

	def _handle_disable(self, user: discord.User, args: list, message) -> discord.Embed:
		member = message.guild.get_member(user.id) if message.guild else None
		has_server_perms = member and (member.guild_permissions.manage_guild or member.guild_permissions.administrator)
		if not is_admin(user.id) and not has_server_perms:
			return error_embed("You don't have permission to use this command.")
		if len(args) != 2:
			return error_embed("Usage: `;;disable <command>` (e.g. `;;disable dream`)")
		cmd_to_disable = args[1].lower()
		if cmd_to_disable not in self.commands or cmd_to_disable in ['disable', 'enable']:
			return error_embed(f"Cannot disable `{cmd_to_disable}`.")
		guild_id = str(message.guild.id)
		if guild_id not in disabled_commands:
			disabled_commands[guild_id] = []
		if cmd_to_disable in disabled_commands[guild_id]:
			return warning_embed(f"`{cmd_to_disable}` is already disabled in this server.")
		disabled_commands[guild_id].append(cmd_to_disable)
		_save_disabled_commands()
		return warning_embed(f"Command `{cmd_to_disable}` has been disabled in this server.", title="🔒 Command Disabled")

	def _handle_enable(self, user: discord.User, args: list, message) -> discord.Embed:
		member = message.guild.get_member(user.id) if message.guild else None
		has_server_perms = member and (member.guild_permissions.manage_guild or member.guild_permissions.administrator)
		if not is_admin(user.id) and not has_server_perms:
			return error_embed("You don't have permission to use this command.")
		if len(args) != 2:
			return error_embed("Usage: `;;enable <command>` (e.g. `;;enable dream`)")
		cmd_to_enable = args[1].lower()
		guild_id = str(message.guild.id)
		if guild_id not in disabled_commands or cmd_to_enable not in disabled_commands[guild_id]:
			return info_embed(f"`{cmd_to_enable}` is not currently disabled in this server.")
		disabled_commands[guild_id].remove(cmd_to_enable)
		_save_disabled_commands()
		return success_embed(f"Command `{cmd_to_enable}` has been re-enabled in this server.", title="🔓 Command Enabled")

	def _handle_delkey(self, user: discord.User, args: list, reply, message) -> discord.Embed:
		"""Admin-only command to delete a key from a user's database.
		Usage 1 (reply): Reply to a bot message with ;;delkey
		Usage 2 (standalone): ;;delkey @user keyname"""
		if not is_admin(user.id):
			return error_embed("You don't have permission to use this command.")

		# Mode 1: Reply to a bot message with ;;delkey
		if reply is not None and len(args) == 1:
			replied_message = reply.resolved
			if replied_message is None:
				return error_embed("Could not fetch the replied message.")

			# The replied message must be from the bot itself
			bot_user = self.get_bot()
			if replied_message.author != bot_user:
				return error_embed("You can only use reply mode on messages sent by the bot.")

			# Build the value to search for from text content + attachments/stickers
			value_to_find = replied_message.content.strip()
			if not value_to_find:
				attachment_text = self._get_attachments_text(replied_message).strip()
				if attachment_text:
					value_to_find = attachment_text
				else:
					return error_embed("The replied message has no text content to match.")

			results = self.db.find_all_keys_by_value(value_to_find)
			if not results:
				return error_embed("Could not find a key matching that message content.")

			deleted_entries = []
			for owner_id, key_name in results:
				self.db.delete_key(owner_id, key_name)
				deleted_entries.append(f"`{key_name}` from <@{owner_id}>")

			embed = discord.Embed(color=discord.Color.red())
			if len(deleted_entries) == 1:
				embed.description = f"Deleted {deleted_entries[0]}"
			else:
				embed.description = "Deleted the following keys:\n" + "\n".join([f"- {e}" for e in deleted_entries])
			return embed

		# Mode 2: ;;delkey @user keyname
		if len(args) == 3:
			target_user_id = extract_user_id(args[1])
			key_name = args[2]

			if target_user_id is None:
				return error_embed("Usage: `;;delkey <@user> <keyname>` or reply to a bot message with `;;delkey`")

			if self.db.delete_key(target_user_id, key_name):
				return discord.Embed(
					description=f"Deleted key `{key_name}` from <@{target_user_id}>'s database.",
					color=discord.Color.red()
				)
			else:
				return error_embed(f"Key `{key_name}` not found for that user.")

		return error_embed("Usage: `;;delkey <@user> <keyname>` or reply to a bot message with `;;delkey`")

	def _handle_steal(self, user: discord.User, args: list, reply) -> discord.Embed:
		if len(args) == 2 and ('<@' in args[1] or args[1].isdigit()):
			return error_embed("Please mention a key to steal: `;;steal @user <key> [new_key]`")
		elif len(args) not in {3, 4}:
			return error_embed("Usage: `;;steal @user <key> [new_key]`")

		steal_from_id = extract_user_id(args[1])
		if steal_from_id is None:
			return error_embed(constants.WRONG_USER_ID)

		old_key = args[2]
		new_key = args[3] if len(args) == 4 else None
		status = steal.steal(self.db.db, user.id, old_key, steal_from_id, new_key)
		if status == constants.SUCCESSFUL:
			dest = f"`{new_key}`" if new_key else f"`{old_key}`"
			return success_embed(f"Successfully stole key `{old_key}` from <@{steal_from_id}> as {dest}!")
		elif status == constants.EMPTY_LIST_STEAL:
			return info_embed(f"<@{steal_from_id}> has not saved any keys yet.")
		elif status == constants.KEY_NOT_FOUND:
			return error_embed(f"Key `{old_key}` not found in <@{steal_from_id}>'s saved keys.")
		elif status == constants.KEY_EXISTS_STEAL:
			return warning_embed(f"You already have a key named `{old_key}`. Specify a new key name: `;;steal @user {old_key} <new_key>`")
		return error_embed(status)

	def _handle_blacklist_add(self, user: discord.User, args: list, reply) -> discord.Embed:
		if not is_admin(user.id):
			return error_embed("You don't have permission to use this command.")
		if len(args) != 2:
			return error_embed("Usage: `;;blacklist_add <@user>`")
		user_id_to_blacklist = extract_user_id(args[1])
		if user_id_to_blacklist is None:
			return error_embed("Invalid user mention or ID.")
		if user_id_to_blacklist in do_not_push.ADMINS:
			return error_embed("You cannot blacklist another admin.")
		if user_id_to_blacklist in constants.BLACKLIST:
			return warning_embed("User is already blacklisted.")
		constants.BLACKLIST.append(user_id_to_blacklist)
		_save_blacklist()
		return discord.Embed(description=f"🚫 User <@{user_id_to_blacklist}> has been blacklisted.", color=discord.Color.dark_red())

	def _handle_blacklist_remove(self, user: discord.User, args: list, reply) -> discord.Embed:
		if not is_admin(user.id):
			return error_embed("You don't have permission to use this command.")
		if len(args) != 2:
			return error_embed("Usage: `;;blacklist_remove <@user>`")
		user_id_to_remove = extract_user_id(args[1])
		if user_id_to_remove is None:
			return error_embed("Invalid user mention or ID.")
		if user_id_to_remove not in constants.BLACKLIST:
			return info_embed("User is not currently blacklisted.")
		constants.BLACKLIST.remove(user_id_to_remove)
		_save_blacklist()
		return success_embed(f"User <@{user_id_to_remove}> has been removed from the blacklist.")

	def _handle_random(self, user: discord.User, args: list) -> Union[str, discord.Embed]:
		if len(args) not in {1, 2}:
			return error_embed("Usage: `;;random [search_term]`")

		search_term = args[1] if len(args) == 2 else None
		return random_key.random_key(self.db.db, user.id, search_term)

	def _handle_grandom(self, user: discord.User, args: list) -> Union[str, discord.Embed]:
		if len(args) not in {1, 2}:
			return error_embed("Usage: `;;grandom [search_term]`")

		search_term = args[1] if len(args) == 2 else None
		return grandom_key.grandom_key(self.db.db, search_term)

	def _handle_search(self, user: discord.User, args: list) -> discord.Embed:
		if len(args) != 2:
			return error_embed("Usage: `;;search <term>`")
		search_key = args[1]
		user_keys = self.db.get_user_keys(user.id)
		matches = sorted([k for k in user_keys if search_key in k])
		if not matches:
			return info_embed(f"No keys found matching `{search_key}`.")
		embed = discord.Embed(
			title=f"Search Results for `{search_key}`",
			description="\n".join([f"- `{k}`" for k in matches]),
			color=discord.Color.blurple()
		)
		embed.set_footer(text=f"Found {len(matches)} match(es)")
		return embed

	def _handle_gsearch(self, user: discord.User, args: list) -> discord.Embed:
		"""Admin-only global search across all users' keys."""
		if not is_admin(user.id):
			return error_embed("You don't have permission to use this command.")
		if len(args) != 2:
			return error_embed("Usage: `;;gsearch <term>`")
		return gsearch.gsearch(self.db.db, args[1])

	async def handle_command(self, user: discord.User, cmd: str, reply=None, message=None) -> Optional[Union[str, discord.File, discord.Embed, dict]]:
		if cmd.startswith(';;'):
			cmd = cmd[2:]

		args = cmd.split()
		if not args:
			return None

		command = args[0]
		if command in self.commands:
			# Check if command is disabled for this server
			if message and hasattr(message, 'guild') and message.guild:
				if is_command_disabled(message.guild.id, command):
					return warning_embed(f"Command `{command}` is disabled in this server.", title="🔒 Command Disabled")
			if command in ['dream', 'deepfry']:
				return await self.commands[command](user, args, reply, message)
			else:
				return self.commands[command](user, args, reply, message)
		return None

	def _handle_help(self, args) -> discord.Embed:
		if len(args) != 2:
			embed = discord.Embed(
				title="CopyPastaBot Help",
				description="Save custom copypastas, recall them dynamically, and use meme commands!",
				color=discord.Color.blurple()
			)
			embed.add_field(
				name="Basic Usage",
				value="• `;;<cmd>` : Run a bot command\n• `;;<key>;;` : Recall a saved text anywhere in your message",
				inline=False
			)
			embed.add_field(
				name="Detailed Categories",
				value="• `;;help copypasta` : Key storage, management, and searching\n• `;;help memes` : Meme generators, image deepfrying, text transformers",
				inline=False
			)
			embed.set_footer(text="Tip: You can attach images or reply to messages when saving keys!")
			return embed

		match args[1].lower():
			case 'copypasta':
				embed = discord.Embed(
					title="Copypasta Commands",
					description="Save, manage, and retrieve your custom copypastas.",
					color=discord.Color.blurple()
				)
				embed.add_field(
					name="Saving & Managing Keys",
					value=(
						"• **`add <key> <message>`** : Save text (or reply to message/attach media)\n"
						"• **`add_o <key> <message>`** : Save text and overwrite if exists\n"
						"• **`saved`** : Interactive paginated list of your saved keys\n"
						"• **`delete <key>`** : Delete a key\n"
						"• **`delete_me`** : Delete all your saved keys\n"
						"• **`rename <old> <new>`** : Rename a key\n"
						"• **`rename_o <old> <new>`** : Rename a key (overwrite)"
					),
					inline=False
				)
				embed.add_field(
					name="Finding & Stealing Keys",
					value=(
						"• **`steal <@user> <key> [new]`** : Steal a key from another user\n"
						"• **`random [term]`** : Send a random saved key (optional search filter)\n"
						"• **`search <term>`** : Search through your saved keys"
					),
					inline=False
				)
				return embed

			case 'memes':
				embed = discord.Embed(
					title="Meme Commands",
					description="Transform text and generate meme media by replying to messages.",
					color=discord.Color.blurple()
				)
				embed.add_field(
					name="Text Transformers (Reply to a message)",
					value=(
						"• **`mock`** : Mock a message with image\n"
						"• **`clap`** : Add 👏 between words\n"
						"• **`zalgo`** : Add cursed text effects\n"
						"• **`owo`** : OwOify text\n"
						"• **`copypasta`** : Generate copypasta emojis\n"
						"• **`stretch`** : Streeeeetch vowels\n"
						"• **`vaporwave`** : Ｃｏｎｖｅｒｔ ｔｏ ｆｕｌｌｗｉｄｔｈ\n"
						"• **`emojify`** : Convert text to 🇪 🇲 🇴 🇯 🇮 🇸\n"
						"• **`s <pattern> <replace> [flags]`** : Vim regex substitute"
					),
					inline=False
				)
				embed.add_field(
					name="Interactive & Media",
					value=(
						"• **`deepfry`** : Deep fry image with eye flares (Reply / Attach)\n"
						"• **`roast <@user>`** : Roast a tagged user\n"
						"• **`flirt <@user>`** : Flirt with a tagged user\n"
						"• **`dream <prompt>`** : AI image & video generation (`-v`, `-i2v`)"
					),
					inline=False
				)
				return embed

			case _:
				return self._handle_help([])

class DiscordBot:
	def __init__(self, token: str):
		self.token = token
		intents = discord.Intents.default()
		intents.message_content = True
		self.client = discord.Client(intents=intents)
		self.db_manager = DatabaseManager(constants.DB_NAME)
		self.command_handler = CommandHandler(self.db_manager, self._get_user)
		
		self.webhook_cache = {}

		print("Loading blacklist...")
		loaded_list = _load_blacklist()
		constants.BLACKLIST.clear()  # Clear the default in-memory list
		constants.BLACKLIST.extend(loaded_list) # Add all loaded IDs
		print(f"Loaded {len(constants.BLACKLIST)} user(s) from blacklist.")

		print("Loading disabled commands...")
		loaded_disabled = _load_disabled_commands()
		disabled_commands.clear()
		disabled_commands.update(loaded_disabled)
		print(f"Loaded disabled commands for {len(disabled_commands)} server(s).")

		self.setup_events()

	def _get_user(self):
		return self.client.user
	
	async def update_status(self):
		while True:
			try:
				total_servers = len(self.client.guilds)
				status = f'Serving users in {total_servers} servers'
				await self.client.change_presence(activity=discord.Activity(
					type=discord.ActivityType.custom,
					name=status,
					state=status
				))
			except Exception as e:
				print(f"Error updating status: {e}", file=sys.stderr)
			await asyncio.sleep(86400)

	async def get_or_create_webhook(self, channel: discord.TextChannel) -> discord.Webhook:
		"""Finds an existing webhook or creates a new one for puppetting."""
		# Check cache first
		if hasattr(channel, 'id') and channel.id in self.webhook_cache:
			return self.webhook_cache[channel.id]
		
		# Check permissions *before* trying
		guild = getattr(channel, 'guild', None)
		if not guild:
			raise discord.Forbidden("Webhooks not supported in non-guild channels.")

		me = guild.me
		if not me or not hasattr(channel, 'permissions_for') or not channel.permissions_for(me).manage_webhooks:
			raise discord.Forbidden("Missing 'Manage Webhooks' permission.")

		if not hasattr(channel, 'webhooks'):
			raise discord.Forbidden("Channel type does not support webhooks.")

		webhooks = await channel.webhooks()
		for wh in webhooks:
			# Find a webhook this bot has created
			if wh.user == self.client.user:
				self.webhook_cache[channel.id] = wh # Cache it
				return wh
		
		# No suitable webhook found, create a new one
		new_webhook = await channel.create_webhook(name=f"{self.client.user.name} Puppeteer")
		self.webhook_cache[channel.id] = new_webhook # Cache it
		return new_webhook

	def setup_events(self):
		@self.client.event
		async def on_ready():
			print(f'Logged in as {self.client.user}')
			asyncio.create_task(self.update_status())

		@self.client.event
		async def on_message(message: discord.Message):
			if message.author == self.client.user or message.author.bot:
				return

			if is_blacklisted(message.author.id):
				if message.content.strip().startswith(';;'):
					await message.reply("You are blacklisted from using this bot.")
				return

			await self.process_message(message)



	async def process_message(self, message: discord.Message):
		content = message.content.strip()
		if content == ';;delmsg':
			await self.handle_delmsg(message)
		elif re.search(constants.REPLACE, content):
			await self.handle_replacement(message)
		elif re.match(constants.COMMAND, content):
			await self.handle_bot_command(message)

	async def handle_delmsg(self, message: discord.Message):
		"""Delete a bot message. Users can delete bot replies to their own messages.
		Bot admins can delete any bot message."""
		if message.reference is None:
			await message.reply(embed=warning_embed("You need to reply to a bot message to use this command."))
			return

		replied_message = message.reference.resolved
		if replied_message is None:
			await message.reply(embed=error_embed("Could not fetch the replied message."))
			return

		# The replied message must be from the bot
		if replied_message.author != self.client.user:
			await message.reply(embed=error_embed("That message was not sent by me."))
			return

		# Check permissions:
		# - Bot admins can delete any bot message
		# - Regular users can only delete bot messages that are replies to their own messages
		user_is_admin = is_admin(message.author.id)

		if not user_is_admin:
			# Check if the bot message is a reply to the user's message
			if replied_message.reference is None:
				await message.reply(embed=error_embed("You can only delete bot messages that are replies to your own messages."))
				return
			# resolved may be None since Discord doesn't recursively resolve references,
			# so fetch the original message via the API if needed
			original_message = replied_message.reference.resolved
			if original_message is None:
				try:
					original_message = await message.channel.fetch_message(replied_message.reference.message_id)
				except (discord.NotFound, discord.HTTPException):
					await message.reply(embed=error_embed("Could not verify the original message author."))
					return
			if original_message.author.id != message.author.id:
				await message.reply(embed=error_embed("You can only delete bot messages that are replies to your own messages."))
				return

		try:
			await replied_message.delete()
		except discord.Forbidden:
			await message.reply(embed=error_embed("I don't have permission to delete that message."))
			return
		except discord.HTTPException as e:
			await message.reply(embed=error_embed(f"Failed to delete: {e}"))
			return

		# Try to also delete the ;;delmsg command message
		try:
			await message.delete()
		except (discord.Forbidden, discord.HTTPException):
			pass

	async def handle_replacement(self, message: discord.Message):
		def get_text(match:re.Match)->str:
			key = match.string[match.start()+2:match.end()-2]
			replacement = self.db_manager.retrieve_text(message.author.id, key)
			if replacement:
				return replacement
			return f';;{key};;'

		replaced_text = re.sub(constants.REPLACE,
				get_text,
				message.content.strip()).strip()
		if replaced_text != message.content.strip() and replaced_text != '':
			target = message.reference.resolved if message.reference else message
			await target.reply(replaced_text)

	async def handle_bot_command(self, message: discord.Message):
		response = await self.command_handler.handle_command(
			message.author, 
			message.content.strip(), 
			reply=message.reference,
			message=message
		)

		if response:
			await self.send_response(message, response)

	async def send_response(self, message: discord.Message, response):
		cmd = message.content.strip()[2:]

		if isinstance(response, dict) and response.get("type") == "puppet":
			author = response["author"]
			content = response["content"]
			channel = response["target_channel"]

			# 1. Get the original username
			original_username = author.display_name

			# 2. Sanitize it:
			# We replace "discord" (case-insensitive) with "disc" + (zero-width space) + "ord".
			# This looks identical to the user but bypasses Discord's filter.
			sanitized_username = re.sub(
				"discord", 
				"dis cord", 
				original_username, 
				flags=re.IGNORECASE
			)

			# 3. Add safety checks for other webhook username rules:
			# - Usernames must be between 1 and 80 characters.
			if len(sanitized_username) > 80:
				sanitized_username = sanitized_username[:80]
			
			# - Usernames cannot be empty or just whitespace.
			if not sanitized_username.strip():
				sanitized_username = "User" # A safe fallback

			try:
				# Get the webhook
				webhook = await self.get_or_create_webhook(channel)
				
				# Send the message using the webhook
				await webhook.send(
					content=content,
					username=sanitized_username,
					avatar_url=author.display_avatar.url
				)

				# Try to delete the user's original command
				try:
					await message.delete()
				except (discord.Forbidden, discord.HTTPException):
					channel_name = getattr(channel, 'name', 'channel')
					print(f"Missing 'Manage Messages' perm in {channel_name}")
				
				return # Stop here, we've sent the message via webhook

			except Exception as e:
				# Clear stale webhook from cache if present
				if hasattr(channel, 'id'):
					self.webhook_cache.pop(channel.id, None)
				
				channel_name = getattr(channel, 'name', 'channel')
				print(f"Webhook failed ({e}). Falling back to normal reply in {channel_name}.")
				response = content # Fall back to sending normal message

		reply_to = message.reference.resolved if message.reference and cmd.split()[0] in {
			'mock', 'deepfry', 'clap', 'zalgo', 'copypasta', 'owo', 'stretch', 'random', 's', 'grandom', 'vaporwave', 'emojify'
		} else message

		if isinstance(response, dict) and response.get("type") == "saved_pagination":
			view = response["view"]
			embed = response["embed"]
			resp = await reply_to.reply(embed=embed, view=view)
			view.message = resp
			return
		elif isinstance(response, discord.File):
			await reply_to.reply(file=response)
			if hasattr(response.fp, 'name') and isinstance(response.fp.name, str) and os.path.exists(response.fp.name):
				try:
					os.remove(response.fp.name)
				except OSError:
					pass
		elif isinstance(response, discord.Embed):
			await reply_to.reply(embed=response)
		elif isinstance(response, str):
			if len(response) > 2000:
				# Always reply to the command message for error responses
				await message.reply("## Fuck me! Keep it under the 2k character limit of Discord.")
			else:
				await reply_to.reply(response)
		else:
			print("Unhandled response type:", type(response))

	def run(self):
		try:
			self.client.run(self.token)
		except Exception as e:
			print(f"Error: {e}")
		finally:
			# To avoid another data loss due to DB file getting deleted while bot is running
			if not os.path.exists(constants.DB_NAME):
				os.makedirs(os.path.dirname(constants.DB_NAME), exist_ok=True)
				open(constants.DB_NAME, 'a').close()
				backup_db = self.db_manager.copy_database(SqliteDict(constants.DB_NAME + '.bkp', autocommit=True))
				backup_db.close()
			self.db_manager.close()

if __name__ == '__main__':
	bot = DiscordBot(do_not_push.API_TOKEN)
	bot.run()