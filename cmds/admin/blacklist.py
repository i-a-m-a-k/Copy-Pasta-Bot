from typing import Optional
import discord
import constants
import do_not_push
from core.config import is_admin, extract_user_id, save_blacklist
from ui.embeds import success_embed, error_embed, warning_embed, info_embed

def handle_blacklist_add(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None
) -> discord.Embed:
	"""Admin-only command to blacklist a user from using the bot."""
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

	constants.BLACKLIST.add(user_id_to_blacklist)
	save_blacklist()
	return discord.Embed(
		description=f"🚫 User <@{user_id_to_blacklist}> has been blacklisted.",
		color=discord.Color.dark_red()
	)

def handle_blacklist_remove(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None
) -> discord.Embed:
	"""Admin-only command to remove a user from the blacklist."""
	if not is_admin(user.id):
		return error_embed("You don't have permission to use this command.")

	if len(args) != 2:
		return error_embed("Usage: `;;blacklist_remove <@user>`")

	user_id_to_remove = extract_user_id(args[1])
	if user_id_to_remove is None:
		return error_embed("Invalid user mention or ID.")

	if user_id_to_remove not in constants.BLACKLIST:
		return info_embed("User is not currently blacklisted.")

	constants.BLACKLIST.discard(user_id_to_remove)
	save_blacklist()
	return success_embed(f"User <@{user_id_to_remove}> has been removed from the blacklist.")
