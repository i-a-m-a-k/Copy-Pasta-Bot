import os
import re
import sys
import logging
import asyncio
from typing import Optional, Union, Callable, Dict
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from pathlib import Path

import discord
from sqlitedict import SqliteDict

import do_not_push
import constants
from cmds import (
	clap, zalgo, forbesify, copypasta, owo, stretch,
	mock, deepfry, delete_me, rename_key, steal
)

sys.path.append(os.path.basename(__file__))

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"bot_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(levelname)s - %(message)s',
	handlers=[
		logging.FileHandler(log_file),
		logging.StreamHandler()
	]
)
logger = logging.getLogger(__name__)

class BotError(Exception):
	"""Base exception class for bot-related errors"""
	pass

class DatabaseError(BotError):
	"""Exception for database-related errors"""
	pass

class CommandError(BotError):
	"""Exception for command-related errors"""
	pass

class CommandResponse(Enum):
	"""Possible command response types"""
	SUCCESS = "success"
	FAILURE = "failure"
	NO_PERMISSION = "no_permission"
	INVALID_ARGS = "invalid_args"
	COOLDOWN = "cooldown"

@dataclass
class CommandResult:
	"""Structured command result"""
	status: CommandResponse
	message: Optional[Union[str, discord.File]] = None
	error: Optional[Exception] = None

class Permission:
	"""Permission management for bot commands"""
	@staticmethod
	def is_admin(user_id: int) -> bool:
		"""Check if user has admin privileges"""
		return user_id in do_not_push.ADMINS

	@staticmethod
	def is_blacklisted(user_id: int) -> bool:
		"""Check if user is blacklisted"""
		return user_id in constants.BLACKLIST

	@staticmethod
	def requires_admin(func: Callable) -> Callable:
		"""Decorator for admin-only commands"""
		async def wrapper(self, user: discord.User, *args, **kwargs):
			if not Permission.is_admin(user.id):
				return CommandResult(
					CommandResponse.NO_PERMISSION,
					"You don't have permission to use this command."
				)
			return await func(self, user, *args, **kwargs)
		return wrapper

class DatabaseManager:
	"""Handles all database operations"""
	
	def __init__(self, db_name: str):
		"""Initialize database manager"""
		self.db_name = db_name
		self.db = SqliteDict(db_name, autocommit=True)
		self._setup_backup_schedule()
		logger.info(f"Database initialized: {db_name}")

	def _setup_backup_schedule(self):
		"""Configure backup scheduling"""
		self.last_backup = datetime.now()
		self.backup_interval = 86400  # 1 day in seconds

	async def _periodic_backup(self):
		"""Perform periodic database backups"""
		current_time = datetime.now()
		if (current_time - self.last_backup).total_seconds() >= self.backup_interval:
			await self.create_backup()
			self.last_backup = current_time

	async def create_backup(self) -> bool:
		"""Create a timestamped backup of the database"""
		backup_dir = Path("backups")
		backup_dir.mkdir(exist_ok=True)
		
		timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
		backup_path = backup_dir / f"{self.db_name}_backup_{timestamp}.sqlite"
		
		try:
			backup_db = SqliteDict(str(backup_path), autocommit=True)
			for key in self.db.keys():
				backup_db[key] = self.db[key]
			backup_db.close()
			logger.info(f"Database backup created: {backup_path}")
			return True
		except Exception as e:
			logger.error(f"Backup failed: {str(e)}")
			if backup_path.exists():
				backup_path.unlink()
			return False

	def store_text(self, user: str, key: str, value: str, overwrite=False) -> CommandResult:
		"""Store text in the database"""
		try:
			user_db = self.db.get(user, {})
			if key in user_db and not overwrite:
				return CommandResult(CommandResponse.FAILURE, constants.KEY_EXISTS_ADD)
			user_db[key] = value
			self.db[user] = user_db
			return CommandResult(CommandResponse.SUCCESS, constants.SUCCESSFUL)
		except Exception as e:
			logger.error(f"Error storing text: {str(e)}")
			raise DatabaseError(f"Failed to store text: {str(e)}")

	def retrieve_text(self, user: str, key: str) -> Optional[str]:
		"""Retrieve text from the database"""
		try:
			return self.db.get(user, {}).get(key)
		except Exception as e:
			logger.error(f"Error retrieving text: {str(e)}")
			return None

	def get_user_keys(self, user: str) -> list:
		"""Get all keys for a user"""
		try:
			return list(self.db.get(user, {}).keys())
		except Exception as e:
			logger.error(f"Error getting user keys: {str(e)}")
			return []

	def delete_key(self, user: str, key: str) -> bool:
		"""Delete a key from the database"""
		try:
			user_db = self.db.get(user, {})
			if key in user_db:
				del user_db[key]
				self.db[user] = user_db
				return True
			return False
		except Exception as e:
			logger.error(f"Error deleting key: {str(e)}")
			return False

	def copy_database(self, new_db: SqliteDict) -> SqliteDict:
		"""Create a copy of the database"""
		try:
			for key in self.db.keys():
				new_db[key] = self.db[key]
			return new_db
		except Exception as e:
			logger.error(f"Error copying database: {str(e)}")
			raise DatabaseError(f"Failed to copy database: {str(e)}")

	def close(self):
		"""Close database connection"""
		try:
			self.db.close()
			logger.info("Database connection closed")
		except Exception as e:
			logger.error(f"Error closing database: {str(e)}")

class CommandHandler:
	"""Handles all bot commands"""
	
	def __init__(self, db_manager: DatabaseManager):
		"""Initialize command handler"""
		self.db = db_manager
		self.command_cooldowns: Dict[str, Dict[int, float]] = {}
		self.setup_commands()
		logger.info("Command handler initialized")

	def setup_commands(self):
		"""Set up command mappings"""
		self.commands = {
			# Core commands
			'add': self._handle_add,
			'add_o': lambda u, a, r: self._handle_add(u, a, r, True),
			'saved': self._handle_saved,
			'delete': self._handle_delete,
			'delete_me': self._handle_delete_me,
			'rename': lambda u, a, r: self._handle_rename(u, a, False),
			'rename_o': lambda u, a, r: self._handle_rename(u, a, True),
			'help': lambda u, a, r: CommandResult(
            CommandResponse.SUCCESS,
            constants.HELP_TEXT
        	),
			'steal': self._handle_steal,

			# Admin commands
			'blacklist_add': self._handle_blacklist_add,
			'blacklist_remove': self._handle_blacklist_remove,
			'backup': self._handle_backup,
			
			# Meme commands
			'clap': self._handle_text_transform('clap'),
			'zalgo': self._handle_text_transform('zalgo'),
			'forbesify': self._handle_text_transform('forbesify'),
			'copypasta': self._handle_text_transform('copypasta'),
			'owo': self._handle_text_transform('owo'),
			'stretch': self._handle_text_transform('stretch'),
			'mock': self._handle_mock,
			'deepfry': self._handle_deepfry,
		}

	async def _check_cooldown(self, user_id: int, command: str) -> bool:
		"""Check if a command is on cooldown"""
		current_time = datetime.now().timestamp()
		if command not in self.command_cooldowns:
			self.command_cooldowns[command] = {}
		
		if user_id in self.command_cooldowns[command]:
			last_used = self.command_cooldowns[command][user_id]
			if current_time - last_used < constants.COMMAND_COOLDOWN:
				return False
		
		self.command_cooldowns[command][user_id] = current_time
		return True

	def _handle_add(self, user: discord.User, args: list, reply, overwrite=False) -> CommandResult:
		"""Handle the add command"""
		if len(args) == 1 or (len(args) == 2 and reply is None):
			return CommandResult(CommandResponse.INVALID_ARGS, constants.WRONG_ARGS_ADD)

		try:
			if len(args) == 2:
				if reply is None:
					return CommandResult(CommandResponse.INVALID_ARGS, constants.WRONG_ARGS_ADD)

				original_message = reply.resolved.content.strip() or ''
				original_message += self._get_attachments_text(reply.resolved)

				if not original_message:
					return CommandResult(CommandResponse.FAILURE, constants.EMPTY_MESSAGE)

				return self.db.store_text(user.id, args[1], original_message, overwrite)

			return self.db.store_text(user.id, args[1], ' '.join(args[2:]), overwrite)
		except Exception as e:
			logger.error(f"Error in add command: {str(e)}")
			return CommandResult(CommandResponse.FAILURE, "Failed to add text")

	def _get_attachments_text(self, message: discord.Message) -> str:
		"""Get text representation of message attachments"""
		text = ''
		for i, attachment in enumerate(message.attachments):
			text += f'[Attachment {i}]({attachment.url}) '
		for sticker in message.stickers:
			text += f'[{sticker.name}]({sticker.url}) '
		return text

	def _handle_saved(self, user: discord.User, args: list, reply) -> CommandResult:
		"""Handle the saved command"""
		try:
			if len(args) == 2 and args[1].startswith('<@') and args[1].endswith('>'):
				if not Permission.is_admin(user.id):
					return CommandResult(
						CommandResponse.NO_PERMISSION,
						"You don't have permission to view another user's keys."
					)
				mentioned_user_id = int(args[1][2:-1])
				keys = self.db.get_user_keys(mentioned_user_id)
				return CommandResult(
					CommandResponse.SUCCESS,
					f"Keys for <@{mentioned_user_id}>:\n- " + '\n- '.join(keys) if keys else constants.EMPTY_LIST
				)

			keys = self.db.get_user_keys(user.id)
			return CommandResult(
				CommandResponse.SUCCESS,
				'- ' + '\n- '.join(keys) if keys else constants.EMPTY_LIST
			)
		except Exception as e:
			logger.error(f"Error in saved command: {str(e)}")
			return CommandResult(CommandResponse.FAILURE, "Failed to retrieve saved items")

	def _handle_delete(self, user: discord.User, args: list, reply) -> CommandResult:
		"""Handle the delete command"""
		if len(args) != 2:
			return CommandResult(CommandResponse.INVALID_ARGS, constants.WRONG_ARGS_DEL)
		
		if self.db.delete_key(user.id, args[1]):
			return CommandResult(CommandResponse.SUCCESS, constants.SUCCESSFUL)
		return CommandResult(CommandResponse.FAILURE, constants.KEY_NOT_FOUND)

	def _handle_delete_me(self, user: discord.User, args: list, reply) -> CommandResult:
		"""Handle the delete_me command"""
		if delete_me.delete_me(self.db.db, user.id):
			return CommandResult(CommandResponse.SUCCESS, constants.SUCCESSFUL)
		return CommandResult(CommandResponse.FAILURE, constants.EMPTY_LIST)

	def _handle_rename(self, user: discord.User, args: list, overwrite: bool) -> CommandResult:
		"""Handle the rename command"""
		if len(args) != 3:
			return CommandResult(CommandResponse.INVALID_ARGS, constants.WRONG_ARGS_DEL)
		
		try:
			status = rename_key.rename_key(self.db.db, user.id, args[1], args[2], overwrite)
			match status:
				case 0: 
					return CommandResult(CommandResponse.SUCCESS, constants.SUCCESSFUL)
				case -1: 
					return CommandResult(CommandResponse.FAILURE, constants.EMPTY_LIST)
				case -2: 
					return CommandResult(CommandResponse.FAILURE, constants.KEY_NOT_FOUND)
				case -3: 
					return CommandResult(CommandResponse.FAILURE, constants.KEY_EXISTS_RENAME if not overwrite else constants.UNSUCCESSFUL)
				case _: 
					return CommandResult(CommandResponse.FAILURE, constants.UNSUCCESSFUL)
		except Exception as e:
			logger.error(f"Error in rename command: {str(e)}")
			return CommandResult(CommandResponse.FAILURE, f"An error occurred: {str(e)}")


	def _handle_text_transform(self, command_type: str) -> Callable:
		"""Create handler for text transformation commands"""
		handlers = {
			'clap': clap.handle_clap_command,
			'zalgo': zalgo.handle_zalgo_command,
			'forbesify': forbesify.handle_forbesify_command,
			'copypasta': copypasta.handle_copypasta_command,
			'owo': owo.handle_owo_command,
			'stretch': stretch.handle_stretch_command
		}

		async def handler(user: discord.User, args: list, reply) -> CommandResult:
			if reply is None:
				return CommandResult(
					CommandResponse.INVALID_ARGS,
					"You need to reply to a message to use this command."
				)
			try:
				result = handlers[command_type](reply)
				return CommandResult(CommandResponse.SUCCESS, result)
			except Exception as e:
				logger.error(f"Error in {command_type} command: {str(e)}")
				return CommandResult(CommandResponse.FAILURE, f"Failed to transform text using {command_type}")

		return handler

	async def _handle_mock(self, user: discord.User, args: list, reply) -> CommandResult:
		"""Handle the mock command"""
		if reply is None:
			return CommandResult(
				CommandResponse.INVALID_ARGS,
				"You need to reply to a message to use this command."
						)
		try:
			result = mock.handle_mock_command(reply)
			return CommandResult(CommandResponse.SUCCESS, result)
		except Exception as e:
			logger.error(f"Error in mock command: {str(e)}")
			return CommandResult(CommandResponse.FAILURE, "Failed to mock the message.")
		
	async def _handle_steal(self, user: discord.User, args: list, reply) -> CommandResult:
		"""Handle the steal command to copy another user's stored key"""
		if len(args) not in {3, 4}:
			return CommandResult(CommandResponse.INVALID_ARGS, constants.WRONG_ARGS)
		
		try:
			steal_from = args[1]
			if not steal_from.startswith('<@') or not steal_from.endswith('>'):
				return CommandResult(CommandResponse.INVALID_ARGS, constants.WRONG_USER_ID)
			
			steal_from_id = int(steal_from[2:-1])  # Extract user ID
			key_to_steal = args[2]
			new_key = args[3] if len(args) == 4 else None  # Optional new key

			# Simulating asynchronous operations, if `steal` module supports async
			result = await asyncio.to_thread(
				steal.steal, self.db.db, user.id, key_to_steal, steal_from_id, new_key
			)

			if result:
				return CommandResult(CommandResponse.SUCCESS, constants.SUCCESSFUL)
			else:
				return CommandResult(CommandResponse.FAILURE, constants.KEY_NOT_FOUND)
		except Exception as e:
			logger.error(f"Error in steal command: {str(e)}")
			return CommandResult(CommandResponse.FAILURE, "Failed to steal the key.")


	async def _handle_deepfry(self, user: discord.User, args: list, reply) -> CommandResult:
		"""Handle the deepfry command"""
		if reply is None:
			return CommandResult(
				CommandResponse.INVALID_ARGS,
				"You need to reply to a message with an image to use this command."
			)
		try:
			result = await deepfry.handle_deepfry_command(reply)
			return CommandResult(CommandResponse.SUCCESS, result)
		except Exception as e:
			logger.error(f"Error in deepfry command: {str(e)}")
			return CommandResult(CommandResponse.FAILURE, "Failed to deepfry the image.")

	@Permission.requires_admin
	async def _handle_blacklist_add(self, user: discord.User, args: list, reply) -> CommandResult:
		"""Handle adding a user to the blacklist"""
		if len(args) != 2 or not args[1].startswith('<@') or not args[1].endswith('>'):
			return CommandResult(CommandResponse.INVALID_ARGS, "Invalid user mention.")
		try:
			user_id_to_blacklist = int(args[1][2:-1])
			if user_id_to_blacklist in do_not_push.ADMINS:
				return CommandResult(
					CommandResponse.FAILURE,
					"You cannot blacklist another admin."
				)
			if user_id_to_blacklist in constants.BLACKLIST:
				return CommandResult(
					CommandResponse.FAILURE,
					"User is already blacklisted."
				)
			constants.BLACKLIST.append(user_id_to_blacklist)
			return CommandResult(
				CommandResponse.SUCCESS,
				f"User <@{user_id_to_blacklist}> has been blacklisted."
			)
		except Exception as e:
			logger.error(f"Error adding to blacklist: {str(e)}")
			return CommandResult(CommandResponse.FAILURE, "Failed to add user to blacklist.")

	@Permission.requires_admin
	async def _handle_blacklist_remove(self, user: discord.User, args: list, reply) -> CommandResult:
		"""Handle removing a user from the blacklist"""
		if len(args) != 2 or not args[1].startswith('<@') or not args[1].endswith('>'):
			return CommandResult(CommandResponse.INVALID_ARGS, "Invalid user mention.")
		try:
			user_id_to_remove = int(args[1][2:-1])
			if user_id_to_remove not in constants.BLACKLIST:
				return CommandResult(
					CommandResponse.FAILURE,
					"User is not blacklisted."
				)
			constants.BLACKLIST.remove(user_id_to_remove)
			return CommandResult(
				CommandResponse.SUCCESS,
				f"User <@{user_id_to_remove}> has been removed from the blacklist."
			)
		except Exception as e:
			logger.error(f"Error removing from blacklist: {str(e)}")
			return CommandResult(CommandResponse.FAILURE, "Failed to remove user from blacklist.")

	@Permission.requires_admin
	async def _handle_backup(self, user: discord.User, args: list, reply) -> CommandResult:
		"""Manually trigger a database backup"""
		try:
			if await self.db.create_backup():
				return CommandResult(
					CommandResponse.SUCCESS,
					"Database backup created successfully."
				)
			return CommandResult(
				CommandResponse.FAILURE,
				"Database backup failed."
			)
		except Exception as e:
			logger.error(f"Error in manual backup: {str(e)}")
			return CommandResult(CommandResponse.FAILURE, "Failed to create a backup.")

	async def handle_command(self, user: discord.User, cmd: str, reply=None) -> Optional[CommandResult]:
		"""Main handler for bot commands"""
		if cmd.startswith(';;'):
			cmd = cmd[2:]

		args = cmd.split()
		if not args:
			return None

		command = args[0]
		if command in self.commands:
			try:
				if not await self._check_cooldown(user.id, command):
					return CommandResult(
						CommandResponse.COOLDOWN,
						f"Command {command} is on cooldown. Please wait."
					)
				handler = self.commands[command]
				if asyncio.iscoroutinefunction(handler):
					return await handler(user, args, reply)
				return handler(user, args, reply)
			except Exception as e:
				logger.error(f"Error handling command {command}: {str(e)}")
				return CommandResult(CommandResponse.FAILURE, f"An error occurred: {str(e)}")
		return CommandResult(CommandResponse.FAILURE, "Unknown command.")

class DiscordBot:
	"""Main bot class"""
	
	def __init__(self, token: str):
		"""Initialize the Discord bot"""
		self.token = token
		intents = discord.Intents.default()
		intents.message_content = True
		self.client = discord.Client(intents=intents)
		self.db_manager = DatabaseManager(constants.DB_NAME)
		self.command_handler = CommandHandler(self.db_manager)
		self.setup_events()

	def setup_events(self):
		"""Set up event listeners for the bot"""
		@self.client.event
		async def on_ready():
			logger.info(f'Logged in as {self.client.user}')

		@self.client.event
		async def on_message(message: discord.Message):
			if message.author == self.client.user or message.author.bot:
				return

			if Permission.is_blacklisted(message.author.id):
				if message.content.strip().startswith(';;'):
					await message.reply("You are blacklisted from using this bot.")
				return

			await self.process_message(message)

	async def process_message(self, message: discord.Message):
		"""Process a Discord message"""
		content = message.content.strip()
		if re.match(constants.REPLACE, content):
			await self.handle_replacement(message)
		elif re.match(constants.COMMAND, content):
			await self.handle_bot_command(message)

	async def handle_replacement(self, message: discord.Message):
		"""Handle a text replacement command"""
		parts = message.content.strip().split(';;')
		replaced_text = self.db_manager.retrieve_text(message.author.id, parts[1])
		if replaced_text:
			target = message.reference.resolved if message.reference else message
			await target.reply(replaced_text)

	async def handle_bot_command(self, message: discord.Message):
		"""Handle a bot command"""
		response = await self.command_handler.handle_command(
			message.author,
			message.content.strip(),
			reply=message.reference
		)

		if response:
			await self.send_response(message, response)

	async def send_response(self, message: discord.Message, response: CommandResult):
		"""Send a response to a Discord message"""
		reply_to = message.reference.resolved if message.reference else message

		if response.status == CommandResponse.SUCCESS and response.message:
			if isinstance(response.message, discord.File):
				await reply_to.reply(file=response.message)
			else:
				await reply_to.reply(response.message)
		elif response.status in {CommandResponse.FAILURE, CommandResponse.NO_PERMISSION, CommandResponse.INVALID_ARGS}:
			await message.reply(response.message or "An error occurred.")

	def run(self):
		"""Run the bot"""
		try:
			self.client.run(self.token)
		except Exception as e:
			logger.error(f"Error running the bot: {str(e)}")
		finally:
			self.db_manager.close()

def main():
	"""Entry point for the bot script."""
	try:
		bot = DiscordBot(do_not_push.API_TOKEN)
		bot.run()
	except KeyboardInterrupt:
		logger.info("Bot shutdown requested by user.")
	except Exception as e:
		logger.error(f"Unexpected error in main: {str(e)}")
	finally:
		logger.info("Bot has exited.")

if __name__ == '__main__':
	main()
