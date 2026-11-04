import difflib
import re
import os
import io
from typing import Optional, Any
import discord
import constants
from core.config import is_admin
from core.database import DatabaseManager
from cmds.chain import split_chain
from ui.embeds import error_embed, warning_embed
from ui.helpers import (
	LOTTIE_STICKER_REGEX,
	APNG_STICKER_REGEX,
	convert_lottie_url_to_gif,
	convert_apng_url_to_gif,
)

def resolve_user_key(db_manager: DatabaseManager, user_id: int, raw_key: str) -> Optional[tuple[str, str]]:
	"""
	Resolves a raw key against a user's database:
	1. Exact match (instant O(1))
	2. Case-insensitive match
	3. Fuzzy typo-tolerant match (similarity >= 0.78, e.g. any2 -> angy2, bhukad -> bhukkad)
	Returns (resolved_key_name, stored_value) or None.
	"""
	# 1. Exact match
	val = db_manager.retrieve_text(user_id, raw_key)
	if val is not None:
		return raw_key, val

	user_keys = db_manager.get_user_keys(user_id)
	if not user_keys:
		return None

	raw_lower = raw_key.lower()

	# 2. Case-insensitive match
	for k in user_keys:
		if k.lower() == raw_lower:
			return k, db_manager.retrieve_text(user_id, k)

	# 3. Fuzzy match for typos
	matches = difflib.get_close_matches(raw_lower, [k.lower() for k in user_keys], n=1, cutoff=0.78)
	if matches:
		matched_lower = matches[0]
		for k in user_keys:
			if k.lower() == matched_lower:
				return k, db_manager.retrieve_text(user_id, k)

	return None

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
			embed=error_embed("Could not resolve replied message."),
			delete_after=constants.AUTO_DELETE_DELAY
		)
		return

	if replied_message.author.id != client.user.id:
		await message.reply(
			embed=error_embed("You can only delete messages sent by me."),
			delete_after=constants.AUTO_DELETE_DELAY
		)
		return

	if not is_admin(message.author.id):
		original_message = replied_message.reference.resolved if replied_message.reference else None
		if original_message is None:
			try:
				if replied_message.reference and replied_message.reference.message_id:
					original_message = await message.channel.fetch_message(replied_message.reference.message_id)
			except (discord.NotFound, discord.Forbidden, discord.HTTPException):
				await message.reply(
					embed=error_embed("Could not verify ownership of this bot reply."),
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

async def handle_replacement(
	db_manager: DatabaseManager,
	message: discord.Message,
	cooldown_manager: Optional[Any] = None
):
	"""Replaces ;;key;; mentions with the user's stored text, lazily converting and caching any Lottie/APNG stickers."""
	matches = list(re.finditer(constants.REPLACE, message.content.strip()))
	if not matches:
		return

	# 1. Resolve keys for this user (exact -> case-insensitive -> fuzzy fallback)
	resolved_matches: list[tuple[Any, str, str]] = []
	for match in matches:
		raw_key = match.string[match.start() + 2 : match.end() - 2]
		res = resolve_user_key(db_manager, message.author.id, raw_key)
		if res:
			resolved_key, val = res
			resolved_matches.append((match, resolved_key, val))

	if not resolved_matches:
		return

	# 2. Cooldown enforcement for key recall (exempt bot admins)
	if cooldown_manager and not is_admin(message.author.id):
		cd_status = cooldown_manager.check(message.author.id, 'key')
		if cd_status is not None:
			time_remaining, expires_timestamp, should_warn = cd_status
			if should_warn:
				first_key = resolved_matches[0][1]
				try:
					await message.reply(
						embed=warning_embed(
							f"You're on cooldown for `;;{first_key};;`. You can use it again <t:{expires_timestamp}:R>.",
							title="⏳ Cooldown Active"
						),
						delete_after=max(1.0, time_remaining)
					)
				except (discord.Forbidden, discord.HTTPException):
					pass
			# Silently ignore further spam during active cooldown window
			return

		# Trigger cooldown for key recall
		cooldown_manager.trigger(message.author.id, 'key')

	target = message.reference.resolved if message.reference else message
	replaced_text = message.content.strip()
	files_to_send: list[tuple[str, str, discord.File]] = []

	for match, resolved_key, val in resolved_matches:
		# 1. Check for Lottie sticker URLs: https://cdn.discordapp.com/stickers/<id>.json
		lottie_matches = list(LOTTIE_STICKER_REGEX.finditer(val))
		for lm in lottie_matches:
			lottie_url = lm.group(0)
			sticker_id = lm.group(1)

			gif_bytes = await convert_lottie_url_to_gif(lottie_url)
			if gif_bytes:
				d_file = discord.File(io.BytesIO(gif_bytes), filename=f"sticker_{sticker_id}.gif")
				files_to_send.append((resolved_key, lottie_url, d_file))

		# 2. Check for APNG sticker URLs: https://cdn.discordapp.com/stickers/<id>.png
		apng_matches = list(APNG_STICKER_REGEX.finditer(val))
		for am in apng_matches:
			apng_url = am.group(0)
			sticker_id = am.group(1)

			gif_bytes = await convert_apng_url_to_gif(apng_url)
			if gif_bytes:
				d_file = discord.File(io.BytesIO(gif_bytes), filename=f"sticker_{sticker_id}.gif")
				files_to_send.append((resolved_key, apng_url, d_file))

		# Replace key token with stored text
		replaced_text = replaced_text.replace(match.group(0), val)

	if replaced_text == message.content.strip() and not files_to_send:
		return

	if files_to_send:
		# Remove raw sticker URLs from the text to be sent alongside the GIF attachment
		clean_text = replaced_text
		for _, sticker_url, _ in files_to_send:
			clean_text = clean_text.replace(sticker_url, "").strip()

		try:
			if len(files_to_send) == 1:
				key, sticker_url, d_file = files_to_send[0]
				sent_msg = await target.reply(
					content=clean_text if clean_text else None,
					file=d_file
				)
				if sent_msg and sent_msg.attachments:
					uploaded_url = sent_msg.attachments[0].url
					current_val = db_manager.retrieve_text(message.author.id, key)
					if current_val:
						updated_val = current_val.replace(sticker_url, uploaded_url)
						db_manager.store_text(message.author.id, key, updated_val, overwrite=True)
			else:
				files = [item[2] for item in files_to_send]
				sent_msg = await target.reply(
					content=clean_text if clean_text else None,
					files=files
				)
				if sent_msg and sent_msg.attachments:
					for idx, (key, sticker_url, _) in enumerate(files_to_send):
						if idx < len(sent_msg.attachments):
							uploaded_url = sent_msg.attachments[idx].url
							current_val = db_manager.retrieve_text(message.author.id, key)
							if current_val:
								updated_val = current_val.replace(sticker_url, uploaded_url)
								db_manager.store_text(message.author.id, key, updated_val, overwrite=True)
			return
		except Exception as e:
			print(f"Error sending/caching converted sticker GIF: {e}")
			# Fall back to sending standard replaced text if file upload fails
			if replaced_text:
				await target.reply(replaced_text)
	elif replaced_text:
		await target.reply(replaced_text)

async def _safe_reply(target: discord.Message, **kwargs) -> Optional[discord.Message]:
	"""
	Reply to a message, falling back to channel.send() if the target
	message was deleted between command invocation and response.
	Returns the sent Message, or None on total failure.
	"""
	try:
		return await target.reply(**kwargs)
	except discord.HTTPException as e:
		if e.code == 50035:  # Invalid Form Body: Unknown message reference
			try:
				return await target.channel.send(**kwargs)
			except (discord.Forbidden, discord.HTTPException):
				return None
		raise
	except discord.Forbidden:
		return None

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
		# Strip mention patterns to prevent @everyone/@here/user mention abuse
		sanitized_username = re.sub(r'@everyone|@here|<@!?\d+>|<@&\d+>', '', sanitized_username)
		# Strip characters Discord webhook API rejects or that enable spoofing
		sanitized_username = re.sub(r'[@#:`]', '', sanitized_username)
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
	command_name = cmd.split()[0].lower() if cmd.split() else ''
	target_reply_cmds = {
		'mock', 'deepfry', 'clap', 'zalgo', 'copypasta', 'owo', 'stretch',
		'random', 's', 'grandom', 'vaporwave', 'emojify', 'dream', 'thonkify', 'dadjoke', 'cat', 'lmgtfy'
	}

	is_chain = len(split_chain(message.content)) > 1

	if message.reference and message.reference.resolved and (command_name in target_reply_cmds or is_chain):
		reply_to = message.reference.resolved
	else:
		reply_to = message

	if isinstance(response, dict):
		if "view" in response:
			view = response["view"]
			kwargs = {"view": view}
			if "embed" in response:
				kwargs["embed"] = response["embed"]
			if "file" in response:
				kwargs["file"] = response["file"]
			if "files" in response:
				kwargs["files"] = response["files"]
			if "content" in response:
				kwargs["content"] = response["content"]
			if "delete_after" in response:
				kwargs["delete_after"] = response["delete_after"]
			resp = await _safe_reply(message, **kwargs)
			if resp and view:
				view.message = resp
			return
		elif "file" in response or "files" in response or "embed" in response or "content" in response:
			kwargs = {}
			if "content" in response:
				kwargs["content"] = response["content"]
			if "embed" in response:
				kwargs["embed"] = response["embed"]
			if "file" in response:
				kwargs["file"] = response["file"]
			if "files" in response:
				kwargs["files"] = response["files"]
			if "delete_after" in response:
				kwargs["delete_after"] = response["delete_after"]
			await _safe_reply(message, **kwargs)
			return
	elif isinstance(response, discord.File):
		# Fallback error images (e.g. thonk_yourself.png) reply directly to the command invoker
		target = message if getattr(response, 'filename', '') == 'thonk_yourself.png' else reply_to
		await _safe_reply(target, file=response)
		if hasattr(response.fp, 'name') and isinstance(response.fp.name, str) and os.path.exists(response.fp.name):
			try:
				os.remove(response.fp.name)
			except OSError:
				pass
	elif isinstance(response, discord.Embed):
		# Content embeds (vibematch, help) should persist permanently.
		# Only transient error/warning notifications auto-delete.
		persistent_embed_cmds = {'vibematch', 'help'}
		if command_name in persistent_embed_cmds:
			await _safe_reply(message, embed=response)
		else:
			await _safe_reply(message, embed=response, delete_after=constants.AUTO_DELETE_DELAY)
	elif isinstance(response, str):
		if len(response) > 2000:
			await _safe_reply(
				message,
				embed=error_embed("Message exceeds Discord's 2,000-character limit."),
				delete_after=constants.AUTO_DELETE_DELAY
			)
		else:
			await _safe_reply(reply_to, content=response)
	else:
		print("Unhandled response type:", type(response))
