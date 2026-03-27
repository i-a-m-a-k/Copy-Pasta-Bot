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

sys.path.append(os.path.basename(__file__))

BLACKLIST_FILE = 'db/blacklist.json'
DISABLED_COMMANDS_FILE = 'db/disabled_commands.json'

# In-memory store: { "guild_id": ["command1", "command2"] }
disabled_commands = {}

def is_admin(user_id: int) -> bool:
	return user_id in do_not_push.ADMINS

def is_blacklisted(user_id: int) -> bool:
	return user_id in constants.BLACKLIST

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

class DatabaseManager:
	def __init__(self, db_name: str):
		self.db = SqliteDict(db_name, autocommit=True)

	def store_text(self, user: str, key: str, value: str, overwrite=False) -> str:
		user_db = self.db.get(user, {})
		if key in user_db and not overwrite:
			return constants.KEY_EXISTS_ADD
		user_db[key] = value
		self.db[user] = user_db
		return constants.SUCCESSFUL

	def retrieve_text(self, user: str, key: str) -> Optional[str]:
		return self.db.get(user, {}).get(key)

	def get_user_keys(self, user: str) -> list:
		return list(self.db.get(user, {}).keys())

	def close(self):
		self.db.close()

	def delete_key(self, user: str, key: str) -> bool:
		user_db = self.db.get(user, {})
		if key in user_db:
			del user_db[key]
			self.db[user] = user_db
			return True
		return False

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
			'enable': lambda u, a, r, m: self._handle_enable(u, a, m)
		}
		self.get_bot = get_bot

	def _handle_add(self, user: discord.User, args: list, reply, message, overwrite=False) -> str:
		if len(args) == 1:
			return constants.WRONG_ARGS_ADD

		if len(args) == 2:
			if reply is None and len(message.attachments) == 0:
				return constants.WRONG_ARGS_ADD

			if reply:
				original_message = reply.resolved.content.strip() or ''
				original_message += self._get_attachments_text(reply.resolved)
			else:
				original_message = ''
			original_message += self._get_attachments_text(message)

			if not original_message:
				return constants.EMPTY_MESSAGE

			return self.db.store_text(user.id, args[1], original_message, overwrite)

		return self.db.store_text(user.id, args[1], ' '.join(args[2:]), overwrite)

	def _get_attachments_text(self, message: discord.Message) -> str:
		text = ''
		for i, attachment in enumerate(message.attachments):
			text += f'[Attachment {i}]({attachment.url}) '
		for sticker in message.stickers:
			text += f'[{sticker.name}]({sticker.url}) '
		return text

	def _handle_saved(self, user: discord.User, args: list, message=None) -> str:
		if len(args) == 2 and args[1].startswith('<@') and args[1].endswith('>'):
			if not is_admin(user.id):
				return "You don't have permission to view another user's keys."
			find_keys_for = args[1][2:-1]
			# keys = sorted(self.db.get_user_keys(mentioned_user_id))
			# return f"Keys for <@{mentioned_user_id}>:\n- " + '\n- '.join(keys) if keys else constants.EMPTY_LIST
		else:
			find_keys_for = user.id

		keys = sorted(self.db.get_user_keys(find_keys_for))
		if len(keys) == 0:
			return constants.EMPTY_LIST
		
		return_text = f'{constants.SAVED_MSGS} <@{str(find_keys_for)}>\n' +\
							'- ' + '\n- '.join(keys) if keys else constants.EMPTY_LIST

		if isinstance(message.channel, discord.TextChannel) or isinstance(message.channel, discord.VoiceChannel):
			if message.channel.permissions_for(message.channel.guild.me).add_reactions and \
						message.channel.permissions_for(message.channel.guild.me).manage_messages:
				return_text = f'{constants.SAVED_MSGS} <@{str(find_keys_for)}>\n1/{str(len(keys)//10 + 1)}\n' +\
								'- ' + '\n- '.join([f'`{k}`' for k in keys[:10]]) if keys else constants.EMPTY_LIST

		return return_text

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

		def handler(user: discord.User, args: list, reply, message=None) -> str:
			if reply is None:
				return "You need to reply to a message to use this command."
			return handlers[command_type](reply)

		return handler

	def _handle_delete(self, user: discord.User, args: list, reply) -> str:
		if len(args) == 1:
			return constants.WRONG_ARGS_DEL
		return constants.SUCCESSFUL if self.db.delete_key(user.id, args[1]) else constants.KEY_NOT_FOUND

	def _handle_delete_me(self, user: discord.User, args: list, reply) -> str:
		return constants.SUCCESSFUL if delete_me.delete_me(self.db.db, user.id) else constants.EMPTY_LIST

	def _handle_rename(self, user: discord.User, args: list, overwrite: bool) -> str:
		if len(args) != 3:
			return constants.WRONG_ARGS_DEL
		status = rename_key.rename_key(self.db.db, user.id, args[1], args[2], overwrite)
		match status:
			case 0: return constants.SUCCESSFUL
			case -1: return constants.EMPTY_LIST
			case -2: return constants.KEY_NOT_FOUND
			case -3: return constants.KEY_EXISTS_RENAME if not overwrite else constants.UNSUCCESSFUL
			case _: return constants.UNSUCCESSFUL

	def _handle_mock(self, user: discord.User, args: list, reply) -> Union[str, discord.File]:
		if reply is None:
			return "You need to reply to a message to use this command."
		return mock.handle_mock_command(reply)
	
	def _handle_flirt(self, user: discord.User, args: list, reply, message) -> str:
		if len(message.mentions) == 0:
			return "You need to mention someone to flirt with! Try ;;flirt @username"
		flirt_text = flirt.handle_flirt_command(message)

		return {
			"type": "puppet",
			"content": flirt_text,  # <-- This string is sent by the puppet
			"author": user,         # <-- This user (the command invoker) is the puppet's identity
			"target_channel": message.channel
		}
	
	def _handle_roast(self, user: discord.User, args: list, reply, message) -> dict:
		# Get the roast text
		roast_text = roast.handle_roast(message, self.get_bot())

		# Return a "puppet" dictionary
		return {
			"type": "puppet",
			"content": roast_text,
			"author": user, # This is message.author
			"target_channel": message.channel
		}

	async def _handle_deepfry(self, user: discord.User, args: list, reply, message=None) -> Union[str, discord.File]:
		if reply is None and (message is None or not message.attachments):
			return "You need to reply to a message with an image to use this command."
		return await deepfry.handle_deepfry_command(reply, message)

	async def _handle_dream(self, user: discord.User, args: list, reply) -> Union[str, discord.File, None]:
		return await dream.handle_dream_command(user, args, message=reply)
		# return "https://cdn.discordapp.com/emojis/1330461299049631764.gif?size=48&animated=true&name=huh%7E2"

	def _handle_disable(self, user: discord.User, args: list, message) -> str:
		member = message.guild.get_member(user.id) if message.guild else None
		has_server_perms = member and (member.guild_permissions.manage_guild or member.guild_permissions.administrator)
		if not is_admin(user.id) and not has_server_perms:
			return "You don't have permission to use this command."
		if len(args) != 2:
			return "Usage: `;;disable <command>` (e.g. `;;disable dream`)"
		cmd_to_disable = args[1].lower()
		if cmd_to_disable not in self.commands or cmd_to_disable in ['disable', 'enable']:
			return f"Cannot disable `{cmd_to_disable}`."
		guild_id = str(message.guild.id)
		if guild_id not in disabled_commands:
			disabled_commands[guild_id] = []
		if cmd_to_disable in disabled_commands[guild_id]:
			return f"`{cmd_to_disable}` is already disabled in this server."
		disabled_commands[guild_id].append(cmd_to_disable)
		_save_disabled_commands()
		return f"`{cmd_to_disable}` has been disabled in this server."

	def _handle_enable(self, user: discord.User, args: list, message) -> str:
		member = message.guild.get_member(user.id) if message.guild else None
		has_server_perms = member and (member.guild_permissions.manage_guild or member.guild_permissions.administrator)
		if not is_admin(user.id) and not has_server_perms:
			return "You don't have permission to use this command."
		if len(args) != 2:
			return "Usage: `;;enable <command>` (e.g. `;;enable dream`)"
		cmd_to_enable = args[1].lower()
		guild_id = str(message.guild.id)
		if guild_id not in disabled_commands or cmd_to_enable not in disabled_commands[guild_id]:
			return f"`{cmd_to_enable}` is not disabled in this server."
		disabled_commands[guild_id].remove(cmd_to_enable)
		_save_disabled_commands()
		return f"`{cmd_to_enable}` has been re-enabled in this server."

	def _handle_steal(self, user: discord.User, args: list, reply) -> str:
		if len(args) == 2 and '<@' in args[1]:
			return constants.WRONG_ARGS_STEAL
		elif len(args) not in {3, 4}:
			return constants.WRONG_ARGS

		steal_from = args[1]
		if not steal_from.startswith('<@') or not steal_from.endswith('>'):
			return constants.WRONG_USER_ID

		steal_from = steal_from[2:-1]
		new_key = args[3] if len(args) == 4 else None
		return steal.steal(self.db.db, user.id, args[2], steal_from, new_key)

	def _handle_blacklist_add(self, user: discord.User, args: list, reply) -> str:
		if not is_admin(user.id):
			return "You don't have permission to use this command."
		if len(args) != 2 or not args[1].startswith('<@') or not args[1].endswith('>'):
			return "Invalid user mention"
		user_id_to_blacklist = int(args[1][2:-1])
		if user_id_to_blacklist in do_not_push.ADMINS:
			return "You cannot blacklist another admin."
		if user_id_to_blacklist in constants.BLACKLIST:
			return "User is already blacklisted."
		constants.BLACKLIST.append(user_id_to_blacklist)
		_save_blacklist()
		return f"User <@{user_id_to_blacklist}> has been blacklisted."

	def _handle_blacklist_remove(self, user: discord.User, args: list, reply) -> str:
		if not is_admin(user.id):
			return "You don't have permission to use this command."
		if len(args) != 2 or not args[1].startswith('<@') or not args[1].endswith('>'):
			return "Invalid user mention"
		user_id_to_remove = int(args[1][2:-1])
		if user_id_to_remove not in constants.BLACKLIST:
			return "User is not blacklisted."
		constants.BLACKLIST.remove(user_id_to_remove)
		_save_blacklist()
		return f"User <@{user_id_to_remove}> has been removed from the blacklist."

	def _handle_random(self, user: discord.User, args:list) -> str:
		if len(args) != 1 and len(args) != 2:
			return constants.WRONG_ARGS
		
		search_term = args[1] if len(args) == 2 else None
		return random_key.random_key(self.db.db, user.id, search_term)

	def _handle_grandom(self, user: discord.User, args:list) -> str:

		if len(args) != 1 and len(args) != 2:
			return constants.WRONG_ARGS
		
		search_term = args[1] if len(args) == 2 else None
		return grandom_key.grandom_key(self.db.db, search_term)

	def _handle_search(self, user: discord.User, args: list) -> str:
		if len(args) != 2:
			return constants.WRONG_ARGS
		return search.search(self.db.db, user.id, args[1])

	async def handle_command(self, user: discord.User, cmd: str, reply=None, message=None) -> Optional[Union[str, discord.File]]:
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
					return f"`{command}` is disabled in this server."
			if command in ['dream', 'deepfry']:
				return await self.commands[command](user, args, reply, message)
			else:
				return self.commands[command](user, args, reply, message)
		return None

	def _handle_help(self, args) -> str:
		if len(args) != 2:
			return constants.HELP_TEXT

		match args[1].lower():
			case 'copypasta':
				return constants.HELP_TEXT_CP
			case 'memes':
				return constants.HELP_TEXT_MEMES
			case _:
				return constants.HELP_TEXT

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
		if channel.id in self.webhook_cache:
			return self.webhook_cache[channel.id]
		
		# Check permissions *before* trying
		me = channel.guild.me
		if not channel.permissions_for(me).manage_webhooks:
			raise discord.Forbidden("Missing 'Manage Webhooks' permission.")

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
		
		@self.client.event
		async def on_reaction_add(reaction, user:discord.User):
			if user == self.client.user:
				return

			message = reaction.message

			if not message.channel.permissions_for(message.channel.guild.me).manage_messages or \
				not message.channel.permissions_for(message.channel.guild.me).add_reactions:
				return

			if message.author != self.client.user:
				return

			if message.created_at < datetime.now(timezone.utc) - timedelta(minutes=5):
				return

			if not message.content.strip().startswith(constants.SAVED_MSGS):
				return

			# Message format:
			# Saved messages for: <@userid>
			# Pageno/total
			# <content>

			message_lines = message.content.strip().split('\n')
			numbers = re.findall(r'\d+', message_lines[0]) # Should only contain 1 element
			if len(numbers) != 1:
				print('Error updating saved message: Can\'t find author id in: ', message_lines[0], file=sys.stderr)
				return

			author = numbers[0]
			if author != str(user.id) and user.id not in do_not_push.ADMINS:
				await reaction.remove(user)
				return
			try:
				page_no = int(message_lines[1].split('/')[0]) - 1
			except ValueError:
				print('Error updating saved message: Can\'t find page no in: ', message_lines[1], file=sys.stderr)
				return
			except Exception as e:
				print('Error updating saved message: Unknown error lmao ' + str(e) , file=sys.stderr)
				return

			user_saved = sorted(self.db_manager.get_user_keys(author))
			pages = [user_saved[i:i+10] for i in range(0, len(user_saved), 10)]

			match reaction.emoji:
				case '▶️':
					new_page = page_no + 1
					if len(pages) <= new_page:
						await reaction.remove(user)
						return
					else:
						new_content = f'{constants.SAVED_MSGS} <@{author}>\n' +\
										f'{str(new_page+1)}/{str(len(pages))}\n' +\
										'- ' + '\n- '.join([f'`{k}`' for k in pages[new_page]])
						await message.edit(content=new_content)

				case '⏭️':
					new_content = f'{constants.SAVED_MSGS} <@{author}>\n' +\
									f'{str(len(pages))}/{str(len(pages))}\n' +\
									'- ' + '\n- '.join([f'`{k}`' for k in pages[-1]])
					await message.edit(content=new_content)

				case '◀️':
					new_page = page_no - 1
					if 0 > new_page:
						await reaction.remove(user)
						return
					else:
						new_content = f'{constants.SAVED_MSGS} <@{author}>\n' +\
										f'{str(new_page+1)}/{str(len(pages))}\n' +\
										'- ' + '\n- '.join([f'`{k}`' for k in pages[new_page]])
						await message.edit(content=new_content)

				case '⏮️':
					new_content = f'{constants.SAVED_MSGS} <@{author}>\n' +\
									f'1/{str(len(pages))}\n' +\
									'- ' + '\n- '.join([f'`{k}`' for k in pages[0]])
					await message.edit(content=new_content)

				case _:
					await reaction.remove(user)
					return

			try:
				# await message.clear_reactions()
				# await message.add_reaction('⏮️')
				# await message.add_reaction('◀️')
				# await message.add_reaction('▶️')
				# await message.add_reaction('⏭️')
				await reaction.remove(user)
			except discord.HTTPException:
				print('Error removing reactions', file=sys.stderr)
			except discord.Forbidden:
				print('This shouldn\'t happen :)', file=sys.stderr)
			except Exception as e:
				print(e, file=sys.stderr)



	async def process_message(self, message: discord.Message):
		content = message.content.strip()
		if re.search(constants.REPLACE, content):
			await self.handle_replacement(message)
		elif re.match(constants.COMMAND, content):
			await self.handle_bot_command(message)

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

			fallback_to_normal_reply = False

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

				# Try to delete the user's original ";;flirt" command
				try:
					await message.delete()
				except discord.Forbidden:
					print(f"Missing 'Manage Messages' perm in {channel.name}")
				
				return # Stop here, we've sent the message

			except discord.Forbidden as e:
				# Bot lacks 'Manage Webhooks' perm. Fall back to a normal reply.
				print(f"{e}. Falling back to normal reply in {channel.name}.")
				response = content # Set response to the text for fallback
				fallback_to_normal_reply = True

			except Exception as e:
				print(f"Error sending webhook: {e}")
				# Send an error message instead
				await message.reply(f"An error occurred: {e}")
				return

			if not fallback_to_normal_reply:
				try:
					# 3. Now, try to delete the original command
					await message.delete()
				except discord.Forbidden:
					# Bot lacks 'Manage Messages' perm, just print and ignore
					print(f"Missing 'Manage Messages' perm in {channel.name} to delete command.")
				except Exception as e:
					# Other error deleting
					print(f"Error deleting original command: {e}")
				return

		reply_to = message.reference.resolved if message.reference and cmd.split()[0] in {
			'mock', 'deepfry', 'clap', 'zalgo', 'copypasta', 'owo', 'stretch', 'random', 's', 'grandom', 'vaporwave', 'emojify'
		} else message

		if isinstance(response, discord.File):
			await reply_to.reply(file=response)
			if hasattr(response.fp, 'name'):
				os.remove(response.fp.name)
		elif isinstance(response, str):
			if len(response) > 2000:
				# Always reply to the command message for error responses
				await message.reply("## Fuck me! Keep it under the 2k character limit of Discord.")
			else:
				resp = await reply_to.reply(response)
				if cmd == 'saved':
					if response.strip().startswith(constants.SAVED_MSGS):
						if isinstance(message.channel, discord.TextChannel) or isinstance(message.channel, discord.VoiceChannel):
							if message.channel.permissions_for(message.channel.guild.me).add_reactions and \
								message.channel.permissions_for(message.channel.guild.me).manage_messages:
								await resp.add_reaction('⏮️')
								await resp.add_reaction('◀️')
								await resp.add_reaction('▶️')
								await resp.add_reaction('⏭️')
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
				os.makedirs(os.path.dirname(constants.DB_NAME))
				os.mknod(constants.DB_NAME)
				backup_db = self.db_manager.copy_database(SqliteDict(constants.DB_NAME + '.bkp', autocommit=True))
				backup_db.close()
			self.db_manager.close()

if __name__ == '__main__':
	bot = DiscordBot(do_not_push.API_TOKEN)
	bot.run()