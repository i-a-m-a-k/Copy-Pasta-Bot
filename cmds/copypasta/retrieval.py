import difflib
import random
from typing import Union, Optional
import discord
from core.config import is_admin, extract_user_id
from core.database import DatabaseManager
from ui.embeds import error_embed, info_embed
from ui.pagination import SavedPaginationView, SavedPromptView

def rank_and_filter_keys(query: str, keys: list[str], max_results: int = 30) -> tuple[list[str], list[str]]:
	"""
	Smart key search ranking with exact, prefix, substring, and fuzzy similarity.
	Returns:
		tuple: (direct_matches, fuzzy_matches)
		- direct_matches: Keys matching via exact, prefix, or substring (case-insensitive).
		- fuzzy_matches: Closely matching keys for typo correction (similarity >= 0.55).
	"""
	if not query or not keys:
		return [], []

	q = query.strip().lower()
	exact = []
	prefix = []
	substring = []
	other_keys = []

	for k in keys:
		k_lower = k.lower()
		if k_lower == q:
			exact.append(k)
		elif k_lower.startswith(q):
			prefix.append(k)
		elif q in k_lower:
			substring.append(k)
		else:
			other_keys.append(k)

	exact.sort()
	prefix.sort()
	substring.sort()

	direct_matches = exact + prefix + substring

	# Fuzzy matching for typo tolerance (when direct matches are empty or sparse)
	fuzzy_matches = []
	if len(direct_matches) < 5 and other_keys:
		scored = []
		for k in other_keys:
			ratio = difflib.SequenceMatcher(None, q, k.lower()).ratio()
			if ratio >= 0.55:
				scored.append((ratio, k))
		scored.sort(key=lambda x: x[0], reverse=True)
		fuzzy_matches = [k for _, k in scored[:10]]

	return direct_matches[:max_results], fuzzy_matches

def handle_saved(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	message: Optional[discord.Message] = None
) -> Union[discord.Embed, dict]:
	"""
	Displays an interactive button prompt to privately view saved keys.
	Clicking the button sends a private ephemeral paginated embed.
	If any other user clicks the button, it dynamically shows their own keys instead.
	Only admins can view another user's saved keys via target mention.
	"""
	target_id = None
	if len(args) == 2:
		target_id = extract_user_id(args[1])
		if target_id is not None:
			if not is_admin(user.id):
				return error_embed("You don't have permission to view another user's keys.")

	view = SavedPromptView(db_manager, target_user_id=target_id)
	desc = (
		f"Click the button below to view saved keys for <@{target_id}>."
		if target_id and is_admin(user.id)
		else "Click the button below to view your saved keys."
	)
	embed = discord.Embed(
		title="🔑 Saved Keys",
		description=desc,
		color=discord.Color.blurple()
	)
	return {
		"type": "saved_prompt",
		"embed": embed,
		"view": view
	}

def handle_random(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str]
) -> Union[str, discord.Embed]:
	"""Returns a random saved key value for the invoking user with smart search filtering."""
	if len(args) not in {1, 2}:
		return error_embed("Usage: `;;random [search_term]`")

	search_term = args[1] if len(args) == 2 else None
	_, user_db = db_manager._get_user_entry(user.id)
	if not user_db:
		return info_embed("You have not saved any keys yet.")

	if search_term is not None:
		q = search_term.strip().lower()
		# 1. Case-insensitive substring match
		matching = [val for key, val in user_db.items() if q in key.lower()]
		# 2. Fuzzy fallback if no substring matches found
		if not matching:
			close_keys = difflib.get_close_matches(q, [k.lower() for k in user_db.keys()], n=5, cutoff=0.55)
			if close_keys:
				for k, val in user_db.items():
					if k.lower() in close_keys:
						matching.append(val)

		if not matching:
			return info_embed(f"No keys found matching `{search_term}`.")
		return random.choice(matching)

	return random.choice(list(user_db.values()))

def handle_grandom(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str]
) -> Union[str, discord.Embed]:
	"""Returns a random saved key value across all users with case-insensitive search."""
	if len(args) not in {1, 2}:
		return error_embed("Usage: `;;grandom [search_term]`")

	q = args[1].strip().lower() if len(args) == 2 else None
	all_values = []

	for user_id, user_db in db_manager.get_all_users().items():
		for key, value in user_db.items():
			if q is None or q in key.lower():
				all_values.append(value)

	if not all_values:
		if q:
			return info_embed(f"No keys found matching `{args[1]}` across any users.")
		return info_embed("No saved text found across any users.")

	return random.choice(all_values)

def handle_search(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str]
) -> discord.Embed:
	"""Searches through the user's saved keys with prefix, substring, and fuzzy matching."""
	if len(args) != 2:
		return error_embed("Usage: `;;search <term>`")

	search_key = args[1]
	user_keys = db_manager.get_user_keys(user.id)
	if not user_keys:
		return info_embed("You have not saved any keys yet.")

	direct_matches, fuzzy_matches = rank_and_filter_keys(search_key, user_keys)

	if not direct_matches and not fuzzy_matches:
		return info_embed(f"No keys found matching `{search_key}`.")

	embed = discord.Embed(
		title=f"🔍 Search Results for `{search_key}`",
		color=discord.Color.blurple()
	)

	description_parts = []
	if direct_matches:
		lines = [f"- `;;{k};;`" for k in direct_matches]
		description_parts.append("\n".join(lines))
		total_count = len(direct_matches)
		footer = f"Found {total_count} match{'es' if total_count != 1 else ''}"
	else:
		footer = "No exact match found"

	if fuzzy_matches:
		fuzzy_header = "**Did you mean:**" if not direct_matches else "**Similar suggestions:**"
		fuzzy_lines = [f"- `;;{k};;`" for k in fuzzy_matches]
		description_parts.append(f"\n{fuzzy_header}\n" + "\n".join(fuzzy_lines))

	full_desc = "\n".join(description_parts)
	if len(full_desc) > 4000:
		full_desc = full_desc[:3990] + "\n\n*(Results truncated...)*"

	embed.description = full_desc
	embed.set_footer(text=footer)
	return embed

def handle_gsearch(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str]
) -> discord.Embed:
	"""Admin-only global search across all users' keys with case-insensitive and smart ranking."""
	if not is_admin(user.id):
		return error_embed("You don't have permission to use this command.")

	if len(args) != 2:
		return error_embed("Usage: `;;gsearch <term>`")

	search_key = args[1]
	sections = []
	total_found = 0

	for user_id, user_db in db_manager.get_all_users().items():
		direct_matches, _ = rank_and_filter_keys(search_key, list(user_db.keys()))
		if direct_matches:
			total_found += len(direct_matches)
			keys_list = '\n'.join([f'- `;;{k};;`' for k in direct_matches[:10]])
			if len(direct_matches) > 10:
				keys_list += f"\n*...and {len(direct_matches) - 10} more*"
			sections.append(f"<@{user_id}>\n{keys_list}")

	embed = discord.Embed(
		title=f"🔍 Global Search: `{search_key}`",
		color=discord.Color.blurple()
	)

	if not sections:
		embed.description = f"No keys found matching `{search_key}` across any users."
	else:
		full_text = '\n\n'.join(sections)
		if len(full_text) > 4000:
			full_text = full_text[:3990] + "\n\n*(Results truncated...)*"
		embed.description = full_text
		embed.set_footer(text=f"Total matches across users: {total_found}")

	return embed
