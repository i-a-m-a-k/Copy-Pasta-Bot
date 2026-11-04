import os
import sys
import re
import asyncio
import discord
from sqlitedict import SqliteDict

import constants
from core.config import (
	load_blacklist,
	load_disabled_commands,
	is_blacklisted,
	disabled_commands,
)
from core.database import DatabaseManager
from core.response_handler import (
	send_response,
	handle_delmsg,
	handle_replacement,
)
from cmds import CommandHandler
from ui.embeds import warning_embed
from ui.helpers import close_http_session

class DiscordBot:
	"""
	Main DiscordBot manager encapsulating Discord client lifecycle,
	event handlers, status loop, and database backup persistence.
	"""
	def __init__(self, token: str):
		self.token = token
		intents = discord.Intents.default()
		intents.message_content = True
		self.client = discord.Client(intents=intents)
		self.db_manager = DatabaseManager(constants.DB_NAME)
		self.command_handler = CommandHandler(
			self.db_manager,
			self._get_user,
			get_client=lambda: self.client
		)
		self.webhook_cache: dict[int, discord.Webhook] = {}
		self._status_task: asyncio.Task | None = None

		print("Loading blacklist...")
		loaded_list = load_blacklist()
		constants.BLACKLIST.clear()
		constants.BLACKLIST.update(loaded_list)
		print(f"Loaded {len(constants.BLACKLIST)} user(s) from blacklist.")

		print("Loading disabled commands...")
		loaded_disabled = load_disabled_commands()
		disabled_commands.clear()
		disabled_commands.update(loaded_disabled)
		print(f"Loaded disabled commands for {len(disabled_commands)} server(s).")

		self.setup_events()

	def _get_user(self) -> discord.ClientUser:
		return self.client.user

	async def update_status(self):
		"""Periodic background task updating the bot presence with server count."""
		while True:
			try:
				total_servers = len(self.client.guilds)
				status = f'Serving users in {total_servers} servers'
				await self.client.change_presence(activity=discord.Activity(
					type=discord.ActivityType.custom,
					name=status,
					state=status
				))
			except asyncio.CancelledError:
				break
			except Exception as e:
				print(f"Error updating status: {e}", file=sys.stderr)
				# Short backoff on failure to avoid tight error loops
				await asyncio.sleep(60)
				continue

			# Normal refresh interval between status updates
			try:
				await asyncio.sleep(86400)
			except asyncio.CancelledError:
				break

	def setup_events(self):
		"""Registers Discord client event listeners."""
		@self.client.event
		async def on_ready():
			print(f'Logged in as {self.client.user}')
			# Cancel previous status task on reconnect to avoid duplicate loops
			if self._status_task and not self._status_task.done():
				self._status_task.cancel()
			self._status_task = asyncio.create_task(self.update_status())

		@self.client.event
		async def on_message(message: discord.Message):
			if message.author == self.client.user or message.author.bot:
				return

			if ';;' not in message.content:
				return

			if is_blacklisted(message.author.id):
				if message.content.strip().startswith(';;'):
					await message.reply(
						embed=warning_embed("You are blacklisted from using this bot."),
						delete_after=constants.AUTO_DELETE_DELAY
					)
				return

			await self.process_message(message)

	async def process_message(self, message: discord.Message):
		"""Routes incoming messages to delmsg, key replacement, or command handler."""
		content = message.content.strip()
		if content == ';;delmsg':
			await handle_delmsg(self.client, message)
		elif re.search(constants.REPLACE, content):
			await handle_replacement(self.db_manager, message, self.command_handler.cooldown_manager)
		elif content.startswith(';;') and len(content) > 2 and not content[2].isspace():
			response = await self.command_handler.handle_command(
				message.author,
				content,
				reply=message.reference,
				message=message
			)
			if response:
				await send_response(self.client, self.webhook_cache, message, response)

	def run(self):
		"""Starts the bot client and ensures safe shutdown and DB backups."""
		try:
			self.client.run(self.token)
		except Exception as e:
			print(f"Error: {e}")
		finally:
			if not os.path.exists(constants.DB_NAME):
				os.makedirs(os.path.dirname(constants.DB_NAME), exist_ok=True)
				open(constants.DB_NAME, 'a').close()
				backup_db = self.db_manager.copy_database(SqliteDict(constants.DB_NAME + '.bkp', autocommit=True))
				backup_db.close()
			self.db_manager.close()
			try:
				asyncio.run(close_http_session())
			except Exception:
				pass
