from typing import Optional, Union, Callable
import asyncio
import discord
import do_not_push
from core.config import is_admin, extract_user_id
from ui.embeds import success_embed, error_embed, warning_embed, info_embed
from ui.pagination import DreamBanlistPromptView
from cmds.memes.dream import (
	add_banned_user,
	is_user_banned,
	remove_banned_user,
	get_banned_users,
)

async def handle_dream_ban(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None,
	message: Optional[discord.Message] = None,
	get_client: Optional[Callable[[], Optional[discord.Client]]] = None
) -> discord.Embed:
	"""Admin-only command to ban a user from using the dream command."""
	if not is_admin(user.id):
		return error_embed("You don't have permission to use this command.")

	user_id_to_ban = None
	username = None
	reason = "Banned by admin"

	replied_msg = None
	if message and message.reference and message.reference.resolved:
		if isinstance(message.reference.resolved, discord.Message):
			replied_msg = message.reference.resolved

	if len(args) > 1:
		extracted_id = extract_user_id(args[1])
		if extracted_id is not None:
			user_id_to_ban = extracted_id
			if len(args) > 2:
				reason = " ".join(args[2:]).strip()
		elif replied_msg:
			user_id_to_ban = replied_msg.author.id
			username = replied_msg.author.name
			reason = " ".join(args[1:]).strip()
	elif replied_msg:
		user_id_to_ban = replied_msg.author.id
		username = replied_msg.author.name

	if user_id_to_ban is None:
		return error_embed("Usage: `;;dream --ban <@user|user_id> [reason]` (or reply to a user's message)")

	if user_id_to_ban in getattr(do_not_push, 'ADMINS', []):
		return error_embed("You cannot ban another admin from dream.")

	if await asyncio.to_thread(is_user_banned, user_id_to_ban):
		return warning_embed(f"User <@{user_id_to_ban}> is already banned from using the dream command.")

	# Resolve username if not already obtained
	if not username:
		# Check message mentions
		if message and hasattr(message, 'mentions'):
			for m in message.mentions:
				if m.id == user_id_to_ban:
					username = m.name
					break

		# Check guild member cache
		if not username and message and getattr(message, 'guild', None):
			member = message.guild.get_member(user_id_to_ban)
			if member:
				username = member.name

		# Check client user cache
		if not username and get_client:
			client = get_client()
			if client:
				u = client.get_user(user_id_to_ban)
				if u:
					username = u.name

		# Fallback to string of user ID
		if not username:
			username = str(user_id_to_ban)

	await asyncio.to_thread(add_banned_user, user_id_to_ban, username, reason)

	return discord.Embed(
		description=f"🚫 User <@{user_id_to_ban}> ({username}) has been banned from using the dream command.\n**Reason:** {reason}",
		color=discord.Color.dark_red()
	)

async def handle_dream_unban(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None,
	message: Optional[discord.Message] = None
) -> discord.Embed:
	"""Admin-only command to unban a user from using the dream command."""
	if not is_admin(user.id):
		return error_embed("You don't have permission to use this command.")

	user_id_to_unban = None

	replied_msg = None
	if message and message.reference and message.reference.resolved:
		if isinstance(message.reference.resolved, discord.Message):
			replied_msg = message.reference.resolved

	if len(args) > 1:
		extracted_id = extract_user_id(args[1])
		if extracted_id is not None:
			user_id_to_unban = extracted_id
		elif replied_msg:
			user_id_to_unban = replied_msg.author.id
	elif replied_msg:
		user_id_to_unban = replied_msg.author.id

	if user_id_to_unban is None:
		return error_embed("Usage: `;;dream --unban <@user|user_id>` (or reply to a user's message)")

	if not await asyncio.to_thread(is_user_banned, user_id_to_unban):
		return info_embed(f"User <@{user_id_to_unban}> is not currently banned from the dream command.")

	removed_rows = await asyncio.to_thread(remove_banned_user, user_id_to_unban)
	if not removed_rows:
		return warning_embed(f"Could not remove user <@{user_id_to_unban}> from the dream banlist.")

	unbanned_name = removed_rows[0].get('username') or str(user_id_to_unban)
	return success_embed(f"User <@{user_id_to_unban}> ({unbanned_name}) has been unbanned from using the dream command.")

async def handle_dream_banlist(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None,
	message: Optional[discord.Message] = None
) -> Union[discord.Embed, dict]:
	"""Admin-only command to view the dream command banlist via private ephemeral prompt."""
	if not is_admin(user.id):
		return error_embed("You don't have permission to use this command.")

	view = DreamBanlistPromptView(get_banned_users_fn=get_banned_users)
	embed = discord.Embed(
		title="🚫 Dream Banlist",
		description="Click the button below to view the dream command banlist privately.",
		color=discord.Color.dark_red()
	)
	return {
		"type": "dream_banlist_prompt",
		"embed": embed,
		"view": view
	}
