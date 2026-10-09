from typing import Optional, Callable
import discord
import constants
from core.config import is_admin
from core.database import DatabaseManager
from ui.embeds import success_embed, error_embed, warning_embed, info_embed
from ui.helpers import get_sticker_media_url

def get_attachments_text(message: discord.Message) -> str:
	"""Formats attached images/files into markdown links and stickers into direct embed URLs."""
	text = ''
	for i, attachment in enumerate(message.attachments):
		text += f'[Attachment {i}]({attachment.url}) '
	for sticker in message.stickers:
		text += f'{get_sticker_media_url(sticker)} '
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
	if len(key_name) > constants.MAX_KEY_LENGTH:
		return error_embed(f"Key name cannot exceed {constants.MAX_KEY_LENGTH} characters (provided length: {len(key_name)}).")

	_, user_db = db_manager._get_user_entry(user.id)
	if key_name not in user_db and len(user_db) >= constants.MAX_KEYS_PER_USER:
		return error_embed(constants.KEY_LIMIT_REACHED, title="❌ Key Limit Exceeded")

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

		if len(original_message) > constants.MAX_VALUE_LENGTH:
			return error_embed(f"Key value exceeds Discord's limit of {constants.MAX_VALUE_LENGTH} characters (current length: {len(original_message)}).")

		status = db_manager.store_text(user.id, key_name, original_message, overwrite)
	else:
		val = ' '.join(args[2:])
		if len(val) > constants.MAX_VALUE_LENGTH:
			return error_embed(f"Key value exceeds Discord's limit of {constants.MAX_VALUE_LENGTH} characters (current length: {len(val)}).")

		status = db_manager.store_text(user.id, key_name, val, overwrite)

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
	if db_manager.clear_user_keys(user.id):
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
	if len(new_key) > constants.MAX_KEY_LENGTH:
		return error_embed(f"New key name cannot exceed {constants.MAX_KEY_LENGTH} characters (provided length: {len(new_key)}).")

	status = db_manager.rename_key(user.id, old_key, new_key, overwrite)
	match status:
		case 0:
			return success_embed(f"Renamed key `{old_key}` to `{new_key}`.")
		case -1:
			return info_embed("You have not saved any keys yet.")
		case -2:
			return error_embed(f"Key `{old_key}` does not exist.")
		case -3:
			return warning_embed(f"Key `{new_key}` already exists. Use `;;rename_o` to overwrite.")
		case -4:
			return error_embed(f"New key name cannot exceed {constants.MAX_KEY_LENGTH} characters.")
		case _:
			return error_embed("Something went wrong while renaming the key.")

def handle_delkey(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference],
	message: discord.Message,
	get_bot: Callable[[], discord.ClientUser]
) -> discord.Embed:
	"""
	Deletes key(s) corresponding to a replied bot message.
	If invoked by an admin: deletes matching keys globally across all users.
	If invoked by a normal user: deletes matching keys from their own database only.
	Usage: Reply to a bot message with ;;delkey
	"""
	if reply is None or len(args) != 1:
		return error_embed("Usage: Reply to a bot message with `;;delkey`")

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

	if is_admin(user.id):
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
	else:
		results = db_manager.find_all_keys_by_value(value_to_find, user=user.id)
		if not results:
			return error_embed("Could not find a key matching that message content in your saved keys.")

		deleted_entries = []
		for owner_id, key_name in results:
			db_manager.delete_key(user.id, key_name)
			deleted_entries.append(f"`{key_name}`")

		embed = discord.Embed(color=discord.Color.red())
		if len(deleted_entries) == 1:
			embed.description = f"Deleted key {deleted_entries[0]} from your saved keys."
		else:
			embed.description = "Deleted the following keys from your saved keys:\n" + "\n".join([f"- {e}" for e in deleted_entries])
		return embed
