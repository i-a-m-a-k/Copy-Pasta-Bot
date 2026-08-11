import re
import os
import discord
import constants
from core.config import is_admin
from core.database import DatabaseManager
from ui.embeds import error_embed, warning_embed

async def get_or_create_webhook(
	client: discord.Client,
	webhook_cache: dict[int, discord.Webhook],
	channel: discord.TextChannel
) -> discord.Webhook:
	"""Finds an existing webhook or creates a new one for puppeting."""
	if hasattr(channel, 'id') and channel.id in webhook_cache:
		return webhook_cache[channel.id]

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
		if wh.user == client.user:
			webhook_cache[channel.id] = wh
			return wh

	new_webhook = await channel.create_webhook(name=f"{client.user.name} Puppeteer")
	webhook_cache[channel.id] = new_webhook
	return new_webhook

async def handle_delmsg(client: discord.Client, message: discord.Message):
	"""
	Deletes a bot message. Users can delete bot replies to their own messages.
	Bot admins can delete any bot message.
	"""
	if message.reference is None:
		await message.reply(
			embed=warning_embed("You need to reply to a bot message to use this command."),
			delete_after=constants.AUTO_DELETE_DELAY
		)
		return

	replied_message = message.reference.resolved
	if replied_message is None:
		await message.reply(
			embed=error_embed("Could not fetch the replied message."),
			delete_after=constants.AUTO_DELETE_DELAY
		)
		return

	if replied_message.author != client.user:
		await message.reply(
			embed=error_embed("That message was not sent by me."),
			delete_after=constants.AUTO_DELETE_DELAY
		)
		return

	user_is_admin = is_admin(message.author.id)

	if not user_is_admin:
		if replied_message.reference is None:
			await message.reply(
				embed=error_embed("You can only delete bot messages that are replies to your own messages."),
				delete_after=constants.AUTO_DELETE_DELAY
			)
			return

		original_message = replied_message.reference.resolved
		if original_message is None:
			try:
				original_message = await message.channel.fetch_message(replied_message.reference.message_id)
			except (discord.NotFound, discord.HTTPException):
				await message.reply(
					embed=error_embed("Could not verify the original message author."),
					delete_after=constants.AUTO_DELETE_DELAY
				)
				return

		if original_message.author.id != message.author.id:
			await message.reply(
				embed=error_embed("You can only delete bot messages that are replies to your own messages."),
				delete_after=constants.AUTO_DELETE_DELAY
			)
			return

	try:
		await replied_message.delete()
	except discord.Forbidden:
		await message.reply(
			embed=error_embed("I don't have permission to delete that message."),
			delete_after=constants.AUTO_DELETE_DELAY
		)
		return
	except discord.HTTPException as e:
		await message.reply(
			embed=error_embed(f"Failed to delete: {e}"),
			delete_after=constants.AUTO_DELETE_DELAY
		)
		return

	try:
		await message.delete()
	except (discord.Forbidden, discord.HTTPException):
		pass

async def handle_replacement(db_manager: DatabaseManager, message: discord.Message):
	"""Replaces ;;key;; mentions with the user's stored text."""
	def get_text(match: re.Match) -> str:
		key = match.string[match.start() + 2 : match.end() - 2]
		replacement = db_manager.retrieve_text(message.author.id, key)
		if replacement:
			return replacement
		return f';;{key};;'

	replaced_text = re.sub(constants.REPLACE, get_text, message.content.strip()).strip()
	if replaced_text != message.content.strip() and replaced_text != '':
		target = message.reference.resolved if message.reference else message
		await target.reply(replaced_text)

async def send_response(
	client: discord.Client,
	webhook_cache: dict[int, discord.Webhook],
	message: discord.Message,
	response
):
	"""
	Dispatches command output to the channel or target message with type handling:
	- puppet: sends via Webhook impersonating user
	- saved_pagination: sends embed with interactive button View
	- discord.File: sends file attachment
	- discord.Embed: sends embed with 60s auto-deletion
	- str: sends text reply (or error embed if >2000 chars)
	"""
	cmd = message.content.strip()[2:]

	if isinstance(response, dict) and response.get("type") == "puppet":
		author = response["author"]
		content = response["content"]
		channel = response["target_channel"]

		original_username = author.display_name
		sanitized_username = re.sub("discord", "dis cord", original_username, flags=re.IGNORECASE)
		if len(sanitized_username) > 80:
			sanitized_username = sanitized_username[:80]
		if not sanitized_username.strip():
			sanitized_username = "User"

		try:
			webhook = await get_or_create_webhook(client, webhook_cache, channel)
			await webhook.send(
				content=content,
				username=sanitized_username,
				avatar_url=author.display_avatar.url
			)
			try:
				await message.delete()
			except (discord.Forbidden, discord.HTTPException):
				channel_name = getattr(channel, 'name', 'channel')
				print(f"Missing 'Manage Messages' perm in {channel_name}")
			return

		except Exception as e:
			if hasattr(channel, 'id'):
				webhook_cache.pop(channel.id, None)
			channel_name = getattr(channel, 'name', 'channel')
			print(f"Webhook failed ({e}). Falling back to normal reply in {channel_name}.")
			response = content

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
		await reply_to.reply(embed=response, delete_after=constants.AUTO_DELETE_DELAY)
	elif isinstance(response, str):
		if len(response) > 2000:
			await message.reply(
				embed=error_embed("Message exceeds Discord's 2,000-character limit."),
				delete_after=constants.AUTO_DELETE_DELAY
			)
		else:
			await reply_to.reply(response)
	else:
		print("Unhandled response type:", type(response))
