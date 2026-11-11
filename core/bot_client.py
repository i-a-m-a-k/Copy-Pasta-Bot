import os
import sys
import re
import asyncio
from typing import Optional
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
from cmds.admin.starboard import (
	load_starboard_config,
	load_starboard_posts,
	starboard_config,
	_posted_messages,
	get_guild_starboards,
	get_starboard_by_emoji,
	get_posted_entry,
	is_already_posted,
	mark_posted,
	unmark_posted,
)
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
		intents.reactions = True
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

		print("Loading starboard config...")
		loaded_starboard = load_starboard_config()
		starboard_config.clear()
		starboard_config.update(loaded_starboard)
		print(f"Loaded starboard config for {len(starboard_config)} server(s).")

		print("Loading starboard post mappings...")
		loaded_posts = load_starboard_posts()
		_posted_messages.clear()
		_posted_messages.update(loaded_posts)
		total_posts = sum(len(m) for boards in _posted_messages.values() for m in boards.values())
		print(f"Loaded {total_posts} starboard post mapping(s).")

		self.setup_events()

	def _get_user(self) -> discord.ClientUser:
		return self.client.user

	@staticmethod
	def _extract_starboard_image(message: discord.Message) -> Optional[str]:
		"""
		Extract the best image URL from a message for the starboard embed.
		Priority: image attachment > embed image > embed thumbnail > sticker.
		"""
		# 1. Image attachments
		if message.attachments:
			for att in message.attachments:
				if att.content_type and att.content_type.startswith('image/'):
					return att.url

		# 2. Embed images / thumbnails
		if message.embeds:
			for emb in message.embeds:
				if emb.image and emb.image.url:
					return emb.image.url
				if emb.thumbnail and emb.thumbnail.url:
					return emb.thumbnail.url

		# 3. Stickers
		if message.stickers:
			from ui.helpers import get_sticker_media_url
			return get_sticker_media_url(message.stickers[0])

		return None

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

		@self.client.event
		async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
			"""Starboard: create or update entries when reactions increase."""
			if payload.guild_id is None:
				return
			await self._process_starboard_reaction(payload)

		@self.client.event
		async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
			"""Starboard: update count or delete entries when reactions decrease."""
			if payload.guild_id is None:
				return
			await self._process_starboard_reaction(payload)

	async def _process_starboard_reaction(self, payload: discord.RawReactionActionEvent):
		"""
		Unified starboard handler for both reaction add and remove events.
		Creates, updates, or deletes starboard entries based on current count.
		"""
		reacted_emoji = str(payload.emoji)

		# Find all starboards in this guild matching the reacted emoji
		matching_boards = get_starboard_by_emoji(payload.guild_id, reacted_emoji)
		if not matching_boards:
			return

		# Don't process reactions from the bot itself
		if payload.user_id == self.client.user.id:
			return

		# Don't starboard messages that are already in a starboard channel
		for sb in matching_boards:
			if payload.channel_id == sb['channel_id']:
				return

		# Fetch the message to count total matching reactions
		try:
			channel = self.client.get_channel(payload.channel_id)
			if channel is None:
				channel = await self.client.fetch_channel(payload.channel_id)
			target_message = await channel.fetch_message(payload.message_id)
		except (discord.NotFound, discord.Forbidden, discord.HTTPException):
			return

		# Count reactions matching the reacted emoji
		reaction_count = 0
		for reaction in target_message.reactions:
			if str(reaction.emoji) == reacted_emoji:
				reaction_count = reaction.count
				break

		# Resolve the replied-to message if the starred message is a reply
		replied_message: Optional[discord.Message] = None
		if target_message.reference and target_message.reference.message_id:
			replied_message = target_message.reference.resolved
			if replied_message is None:
				try:
					replied_message = await channel.fetch_message(target_message.reference.message_id)
				except (discord.NotFound, discord.Forbidden, discord.HTTPException):
					pass

		# Process each matching starboard
		for sb in matching_boards:
			existing_sb_msg_id = get_posted_entry(payload.guild_id, sb['name'], payload.message_id)
			meets_threshold = reaction_count >= sb['threshold']

			if existing_sb_msg_id is not None and existing_sb_msg_id > 0 and not meets_threshold:
				# --- Below threshold: delete from starboard ---
				# Always unmark first to prevent stale mappings on failure
				unmark_posted(payload.guild_id, sb['name'], payload.message_id)
				starboard_channel = self.client.get_channel(sb['channel_id'])
				if starboard_channel is None:
					try:
						starboard_channel = await self.client.fetch_channel(sb['channel_id'])
					except (discord.NotFound, discord.Forbidden):
						continue
				try:
					sb_msg = await starboard_channel.fetch_message(existing_sb_msg_id)
					await sb_msg.delete()
				except (discord.NotFound, discord.Forbidden, discord.HTTPException):
					pass  # Already deleted or inaccessible; mapping already cleared

			elif existing_sb_msg_id is not None and existing_sb_msg_id > 0 and meets_threshold:
				# --- Above threshold: update the count in the embed ---
				starboard_channel = self.client.get_channel(sb['channel_id'])
				if starboard_channel is None:
					try:
						starboard_channel = await self.client.fetch_channel(sb['channel_id'])
					except (discord.NotFound, discord.Forbidden):
						continue
				try:
					sb_msg = await starboard_channel.fetch_message(existing_sb_msg_id)
					embed = self._build_starboard_embed(
						target_message, replied_message, reacted_emoji,
						reaction_count, channel
					)
					await sb_msg.edit(embed=embed)
				except discord.NotFound:
					# Starboard message was manually deleted; clear stale mapping
					# so a future threshold meet creates a fresh entry
					unmark_posted(payload.guild_id, sb['name'], payload.message_id)
				except (discord.Forbidden, discord.HTTPException):
					pass

			elif existing_sb_msg_id is not None and existing_sb_msg_id == 0:
				# Placeholder from a concurrent send in progress — skip to avoid duplicates
				continue

			elif existing_sb_msg_id is None and meets_threshold:
				# --- Not posted yet and meets threshold: create new entry ---
				starboard_channel = self.client.get_channel(sb['channel_id'])
				if starboard_channel is None:
					try:
						starboard_channel = await self.client.fetch_channel(sb['channel_id'])
					except (discord.NotFound, discord.Forbidden):
						print(f"Starboard channel {sb['channel_id']} not found for guild {payload.guild_id}")
						continue

				embed = self._build_starboard_embed(
					target_message, replied_message, reacted_emoji,
					reaction_count, channel
				)

				# Mark posted BEFORE sending to prevent race-condition duplicates.
				# Use a placeholder (0) — updated with real ID after send succeeds.
				mark_posted(payload.guild_id, sb['name'], payload.message_id, 0)

				try:
					sent_msg = await starboard_channel.send(embed=embed)
					# Update mapping with the real starboard message ID
					mark_posted(payload.guild_id, sb['name'], payload.message_id, sent_msg.id)
				except (discord.Forbidden, discord.HTTPException) as e:
					# Roll back the placeholder on failure
					unmark_posted(payload.guild_id, sb['name'], payload.message_id)
					print(f"Failed to post to starboard '{sb['name']}' in guild {payload.guild_id}: {e}")

	def _build_starboard_embed(
		self,
		target_message: discord.Message,
		replied_message: Optional[discord.Message],
		reacted_emoji: str,
		reaction_count: int,
		channel
	) -> discord.Embed:
		"""Build the starboard embed for a message."""
		author = target_message.author
		embed = discord.Embed(
			description=target_message.content[:2000] if target_message.content else None,
			color=discord.Color.gold(),
			timestamp=target_message.created_at
		)
		embed.set_author(
			name=author.display_name,
			icon_url=author.display_avatar.url
		)
		embed.set_footer(text=f"{reacted_emoji} {reaction_count} • #{getattr(channel, 'name', 'unknown')}")

		# --- Main message media ---
		main_image_url = self._extract_starboard_image(target_message)
		if main_image_url:
			embed.set_image(url=main_image_url)

		# --- Replied-to message context ---
		if replied_message:
			replied_author = replied_message.author
			replied_content = replied_message.content.strip() if replied_message.content else ''

			replied_image_url = self._extract_starboard_image(replied_message)
			has_replied_media = replied_image_url is not None
			has_replied_attachments = bool(replied_message.attachments)
			has_replied_stickers = bool(replied_message.stickers)

			if replied_content:
				preview = replied_content[:300]
				if len(replied_content) > 300:
					preview += '...'
				reply_text = preview
			elif has_replied_media or has_replied_attachments:
				reply_text = '*[Media]*'
			elif has_replied_stickers:
				reply_text = '*[Sticker]*'
			elif replied_message.embeds:
				reply_text = '*[Embed]*'
			else:
				reply_text = '*[No content]*'

			embed.add_field(
				name=f"↩️ Replying to {replied_author.display_name}",
				value=reply_text,
				inline=False
			)

			# If the main message has no image but the replied-to does, use it
			if not embed.image and replied_image_url:
				embed.set_image(url=replied_image_url)

		embed.add_field(
			name="Source",
			value=f"[Jump to message]({target_message.jump_url})",
			inline=False
		)

		return embed

	async def process_message(self, message: discord.Message):
		"""Routes incoming messages to delmsg, key replacement, or command handler."""
		content = message.content.strip()
		if content == ';;delmsg':
			await handle_delmsg(self.client, message)
		elif re.search(constants.REPLACE, content) and not self.command_handler.is_chain(content):
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
