from typing import Optional, Union
import discord
import constants
from core.config import extract_user_id
from core.database import DatabaseManager
from ui.embeds import success_embed, error_embed, warning_embed, info_embed

def handle_steal(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None
) -> discord.Embed:
	"""Allows a user to copy/steal a key from another user into their own database."""
	if len(args) == 2 and ('<@' in args[1] or args[1].isdigit()):
		return error_embed("Please mention a key to steal: `;;steal @user <key> [new_key]`")
	elif len(args) not in {3, 4}:
		return error_embed("Usage: `;;steal @user <key> [new_key]`")

	steal_from_id = extract_user_id(args[1])
	if steal_from_id is None:
		return error_embed(constants.WRONG_USER_ID)

	old_key = args[2]
	new_key = args[3] if len(args) == 4 else None

	_, target_user_db = db_manager._get_user_entry(steal_from_id)
	if not target_user_db:
		return info_embed(f"<@{steal_from_id}> has not saved any keys yet.")

	value = target_user_db.get(old_key)
	if value is None:
		return error_embed(f"Key `{old_key}` not found in <@{steal_from_id}>'s saved keys.")

	key_user, invoking_user_db = db_manager._get_user_entry(user.id)
	target_key_name = new_key if new_key else old_key

	if target_key_name in invoking_user_db:
		return warning_embed(f"You already have a key named `{target_key_name}`. Specify a new key name: `;;steal @user {old_key} <new_key>`")

	db_manager.store_text(user.id, target_key_name, value, overwrite=False)

	dest = f"`{new_key}`" if new_key else f"`{old_key}`"
	return success_embed(f"Successfully stole key `{old_key}` from <@{steal_from_id}> as {dest}!")
