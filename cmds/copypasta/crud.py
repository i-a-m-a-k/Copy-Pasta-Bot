from typing import Optional, Union, Callable
import discord
import constants
from core.config import is_admin, extract_user_id
from core.database import DatabaseManager
from ui.embeds import success_embed, error_embed, warning_embed, info_embed

def get_attachments_text(message: discord.Message) -> str:
	"""Formats attached images/files and stickers into markdown links."""
	text = ''
	for i, attachment in enumerate(message.attachments):
		text += f'[Attachment {i}]({attachment.url}) '
	for sticker in message.stickers:
		text += f'[{sticker.name}]({sticker.url}) '
	return text

def handle_add(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference],
	message: discord.Message,
	overwrite: bool = False
) -> discord.Embed:
	"""Saves or updates a custom text snippet for the invoking user."""
	if len(args) == 1:
		return error_embed("Usage: `;;add <key> <value>` or `;;add <key>` (replying to a message / adding an attachment)")

	key_name = args[1]

	if len(args) == 2:
		if reply is None and len(message.attachments) == 0:
			return error_embed("Usage: `;;add <key> <value>` or `;;add <key>` (replying to a message / adding an attachment)")

		if reply:
			original_message = (reply.resolved.content.strip() if hasattr(reply.resolved, 'content') else '') or ''
			original_message += get_attachments_text(reply.resolved)
		else:
			original_message = ''
		original_message += get_attachments_text(message)

		if not original_message:
			return error_embed(constants.EMPTY_MESSAGE)

		status = db_manager.store_text(user.id, key_name, original_message, overwrite)
	else:
		status = db_manager.store_text(user.id, key_name, ' '.join(args[2:]), overwrite)

	if status == constants.SUCCESSFUL:
		action = "overwritten" if overwrite else "saved"
		return success_embed(f"Key `{key_name}` has been {action} successfully!")
	elif status == constants.KEY_EXISTS_ADD:
		return warning_embed(f"Key `{key_name}` already exists. Use `;;add_o` to overwrite.")
	return error_embed(status)

def handle_delete(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None
) -> discord.Embed:
	"""Deletes a specific key owned by the user."""
	if len(args) == 1:
		return error_embed("Usage: `;;delete <key>`")
	key_name = args[1]
	if db_manager.delete_key(user.id, key_name):
		return success_embed(f"Deleted key `{key_name}` from your saved keys.")
	return error_embed(f"Key `{key_name}` does not exist.")

def handle_delete_me(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None
) -> discord.Embed:
	"""Mass deletes all keys saved by the user."""
	user_id, user_db = db_manager._get_user_entry(user.id)
	if user_db:
		user_db.clear()
		db_manager.db[user_id] = user_db
		return success_embed("All your saved keys have been deleted.")
	return info_embed("You don't have any saved keys to delete.")

def handle_rename(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	overwrite: bool = False
) -> discord.Embed:
	"""Renames an existing key for the user."""
	if len(args) != 3:
		cmd_name = "rename_o" if overwrite else "rename"
		return error_embed(f"Usage: `;;{cmd_name} <original_key> <new_key>`")

	old_key, new_key = args[1], args[2]
	key_user, user_db = db_manager._get_user_entry(user.id)
	if not user_db:
		return info_embed("You have not saved any keys yet.")
	if old_key not in user_db:
		return error_embed(f"Key `{old_key}` does not exist.")
	if new_key in user_db and not overwrite:
		return warning_embed(f"Key `{new_key}` already exists. Use `;;rename_o` to overwrite.")

	user_db[new_key] = user_db.pop(old_key)
	db_manager.db[key_user] = user_db
	return success_embed(f"Renamed key `{old_key}` to `{new_key}`.")

def handle_delkey(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference],
	message: discord.Message,
	get_bot: Callable[[], discord.ClientUser]
) -> discord.Embed:
	"""
	Admin-only command to delete a key from a user's database.
	Usage 1 (reply): Reply to a bot message with ;;delkey
	Usage 2 (standalone): ;;delkey @user keyname
	"""
	if not is_admin(user.id):
		return error_embed("You don't have permission to use this command.")

	# Mode 1: Reply to a bot message with ;;delkey
	if reply is not None and len(args) == 1:
		replied_message = reply.resolved
		if replied_message is None:
			return error_embed("Could not fetch the replied message.")

		bot_user = get_bot()
		if replied_message.author != bot_user:
			return error_embed("You can only use reply mode on messages sent by the bot.")

		value_to_find = replied_message.content.strip()
		if not value_to_find:
			attachment_text = get_attachments_text(replied_message).strip()
			if attachment_text:
				value_to_find = attachment_text
			else:
				return error_embed("The replied message has no text content to match.")

		results = db_manager.find_all_keys_by_value(value_to_find)
		if not results:
			return error_embed("Could not find a key matching that message content.")

		deleted_entries = []
		for owner_id, key_name in results:
			db_manager.delete_key(owner_id, key_name)
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

		if db_manager.delete_key(target_user_id, key_name):
			return discord.Embed(
				description=f"Deleted key `{key_name}` from <@{target_user_id}>'s database.",
				color=discord.Color.red()
			)
		else:
			return error_embed(f"Key `{key_name}` not found for that user.")

	return error_embed("Usage: `;;delkey <@user> <keyname>` or reply to a bot message with `;;delkey`")
