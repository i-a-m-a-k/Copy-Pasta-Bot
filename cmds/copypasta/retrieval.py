import random
from typing import Union, Optional
import discord
from core.config import is_admin, extract_user_id
from core.database import DatabaseManager
from ui.embeds import error_embed, info_embed
from ui.pagination import SavedPaginationView

def handle_saved(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	message: Optional[discord.Message] = None
) -> Union[discord.Embed, dict]:
	"""
	Displays an interactive paginated embed list of saved keys.
	Only admins can view another user's saved keys.
	"""
	if len(args) == 2:
		target_id = extract_user_id(args[1])
		if target_id is not None:
			if not is_admin(user.id):
				return error_embed("You don't have permission to view another user's keys.")
			find_keys_for = target_id
		else:
			find_keys_for = user.id
	else:
		find_keys_for = user.id

	keys = sorted(db_manager.get_user_keys(find_keys_for))
	if len(keys) == 0:
		msg = "You have not saved any keys yet." if find_keys_for == user.id else f"<@{find_keys_for}> has not saved any keys yet."
		return info_embed(msg)

	view = SavedPaginationView(invoking_user_id=user.id, target_user_id=find_keys_for, keys=keys)
	return {
		"type": "saved_pagination",
		"embed": view.get_embed(),
		"view": view
	}

def handle_random(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str]
) -> Union[str, discord.Embed]:
	"""Returns a random saved key value for the invoking user with optional term filter."""
	if len(args) not in {1, 2}:
		return error_embed("Usage: `;;random [search_term]`")

	search_term = args[1] if len(args) == 2 else None
	_, user_db = db_manager._get_user_entry(user.id)
	if not user_db:
		return info_embed("You have not saved any keys yet.")

	if search_term is not None:
		matching = [val for key, val in user_db.items() if search_term in key]
		if not matching:
			return info_embed(f"No keys found matching `{search_term}`.")
		return random.choice(matching)

	return random.choice(list(user_db.values()))

def handle_grandom(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str]
) -> Union[str, discord.Embed]:
	"""Returns a random saved key value across all users in the bot."""
	if len(args) not in {1, 2}:
		return error_embed("Usage: `;;grandom [search_term]`")

	search_term = args[1] if len(args) == 2 else None
	all_values = []

	for user_id in db_manager.db.keys():
		user_db = db_manager.db.get(user_id, {})
		for key, value in user_db.items():
			if search_term is None or search_term in key:
				all_values.append(value)

	if not all_values:
		if search_term:
			return info_embed(f"No keys found matching `{search_term}` across any users.")
		return info_embed("No saved text found across any users.")

	return random.choice(all_values)

def handle_search(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str]
) -> discord.Embed:
	"""Searches through the user's saved keys and returns matching names."""
	if len(args) != 2:
		return error_embed("Usage: `;;search <term>`")

	search_key = args[1]
	user_keys = db_manager.get_user_keys(user.id)
	matches = sorted([k for k in user_keys if search_key in k])

	if not matches:
		return info_embed(f"No keys found matching `{search_key}`.")

	embed = discord.Embed(
		title=f"Search Results for `{search_key}`",
		description="\n".join([f"- `{k}`" for k in matches]),
		color=discord.Color.blurple()
	)
	embed.set_footer(text=f"Found {len(matches)} match(es)")
	return embed

def handle_gsearch(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str]
) -> discord.Embed:
	"""Admin-only global search across all users' keys."""
	if not is_admin(user.id):
		return error_embed("You don't have permission to use this command.")

	if len(args) != 2:
		return error_embed("Usage: `;;gsearch <term>`")

	search_key = args[1]
	sections = []

	for user_id in db_manager.db.keys():
		user_db = db_manager.db.get(user_id, {})
		matching_keys = sorted([key for key in user_db.keys() if search_key in key])
		if matching_keys:
			keys_list = '\n'.join([f'- `{k}`' for k in matching_keys])
			sections.append(f"<@{user_id}>\n{keys_list}")

	embed = discord.Embed(
		title=f"Global search: `{search_key}`",
		color=discord.Color.blurple()
	)

	if not sections:
		embed.description = "No keys found matching that term."
	else:
		full_text = '\n\n'.join(sections)
		if len(full_text) > 4096:
			full_text = full_text[:4090] + "\n..."
		embed.description = full_text

	return embed
