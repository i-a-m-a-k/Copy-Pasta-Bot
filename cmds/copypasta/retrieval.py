import asyncio
import difflib
import random
from typing import Union, Optional
import discord
from core.config import is_admin, extract_user_id
from core.database import DatabaseManager
from ui.embeds import error_embed, info_embed
from ui.pagination import SavedPromptView
from .crud import get_attachments_text
from .vibematch import clean_value

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
	"""
	Returns a random saved key value for the invoking user with smart search filtering.
	Excludes recently shown values (tracked by value content, not key name).
	Shares history with grandom command.
	"""
	if len(args) not in {1, 2}:
		return error_embed("Usage: `;;random [search_term]`")

	search_term = args[1] if len(args) == 2 else None
	_, user_db = db_manager._get_user_entry(user.id)
	if not user_db:
		return info_embed("You have not saved any keys yet.")

	# Get shared history cache
	history_cache = db_manager.get_random_history_cache()
	excluded_values = history_cache.get_excluded_values(user.id)

	if search_term is not None:
		q = search_term.strip().lower()
		# 1. Case-insensitive substring match (exclude history)
		matching = [
			val for key, val in user_db.items() 
			if q in key.lower() and val not in excluded_values
		]
		# 2. Fuzzy fallback if no substring matches found
		if not matching:
			close_keys = difflib.get_close_matches(q, [k.lower() for k in user_db.keys()], n=5, cutoff=0.55)
			if close_keys:
				for k, val in user_db.items():
					if k.lower() in close_keys and val not in excluded_values:
						matching.append(val)

		if not matching:
			# Fallback: include history values if no matches found
			matching = [val for key, val in user_db.items() if q in key.lower()]
			if not matching:
				return info_embed(f"No keys found matching `{search_term}`.")
		
		selected = random.choice(matching)
		history_cache.add_to_history(user.id, selected)
		return selected

	# No search term - get all values excluding history
	available = [val for val in user_db.values() if val not in excluded_values]
	
	if not available:
		# All values in history, use full set
		available = list(user_db.values())
	
	selected = random.choice(available)
	history_cache.add_to_history(user.id, selected)
	return selected

def handle_grandom(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str]
) -> Union[str, discord.Embed]:
	"""
	Returns a random saved key value across all users with case-insensitive search.
	Deduplicates by value content (same value from different users only appears once).
	Excludes recently shown values (shares history with random command).
	"""
	if len(args) not in {1, 2}:
		return error_embed("Usage: `;;grandom [search_term]`")

	search_term = args[1].strip().lower() if len(args) == 2 else None
	
	# Get shared history cache
	history_cache = db_manager.get_random_history_cache()
	excluded_values = history_cache.get_excluded_values(user.id)
	
	# Build set of unique values (automatically deduplicates)
	seen = set()
	unique_values = []

	for user_id_db, user_db in db_manager.get_all_users().items():
		for key, value in user_db.items():
			# Skip if already seen (deduplication)
			if value in seen:
				continue
			
			# Skip if in user's history
			if value in excluded_values:
				continue
			
			# Apply search filter if provided
			if search_term and search_term not in key.lower():
				continue
			
			# Add to unique values
			seen.add(value)
			unique_values.append(value)

	if not unique_values:
		# Fallback: include history values if no matches found
		for user_id_db, user_db in db_manager.get_all_users().items():
			for key, value in user_db.items():
				if value in seen:
					continue
				if search_term and search_term not in key.lower():
					continue
				seen.add(value)
				unique_values.append(value)
		
		if not unique_values:
			if search_term:
				return info_embed(f"No keys found matching `{args[1]}` across any users.")
			return info_embed("No saved text found across any users.")

	selected = random.choice(unique_values)
	history_cache.add_to_history(user.id, selected)
	return selected

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

# --- Reverse Search (value -> keys) ---

REVSEARCH_MAX_RESULTS = 15
# Minimum length of a text segment to be considered for matching.
# Prevents trivial matches on punctuation, single words, etc.
REVSEARCH_MIN_SEGMENT_LEN = 4

def _split_segments(text: str) -> tuple[str, list[str]]:
	"""
	Splits normalized text into (text_part, media_urls).
	Extracts URLs (http/https) as separate segments so media can be matched
	independently of surrounding text. Markdown link wrappers like
	'[attachment 0](url)' are collapsed to just the URL so the label noise
	doesn't block media-only matches.
	Returns (remaining_text_stripped, list_of_urls).
	"""
	import re as _re
	# First unwrap markdown links: [label](url) -> url
	MD_LINK_RE = _re.compile(r'\[[^\]]*\]\((https?://[^\s\)]+)\)')
	text = MD_LINK_RE.sub(r'\1', text)
	URL_RE = _re.compile(r'https?://[^\s\)]+')
	urls = URL_RE.findall(text)
	remaining = URL_RE.sub(' ', text).strip()
	# Collapse whitespace runs
	remaining = _re.sub(r'\s+', ' ', remaining)
	return remaining, urls

def _segments_match(query_text: str, value_text: str) -> bool:
	"""
	Checks whether the query is contained within the stored value (or
	vice-versa) using segment-level containment:
	- Every media URL in the smaller set must appear in the larger set
	- The text portion of the smaller must be a substring of the larger's text
	  (trivial text — markdown wrappers, punctuation — is ignored)
	Both directions are checked: query⊆value and value⊆query.
	"""
	import re as _re

	def _is_trivial_text(t: str) -> bool:
		"""Text that carries no semantic content: brackets, punctuation, spaces."""
		return len(t) < REVSEARCH_MIN_SEGMENT_LEN or not _re.search(r'[a-z0-9]', t)

	q_text, q_urls = _split_segments(query_text)
	v_text, v_urls = _split_segments(value_text)

	def _contains(a_text: str, a_urls: list[str], b_text: str, b_urls: list[str]) -> bool:
		"""Returns True if all meaningful segments of A are contained in B."""
		# All A URLs must be present in B URLs
		for url in a_urls:
			if url not in b_urls:
				return False
		# Text containment: skip when A's text is trivial (markdown noise, empty)
		if not _is_trivial_text(a_text) and a_text not in b_text:
			return False
		# Must have matched at least one meaningful segment
		if not a_urls and _is_trivial_text(a_text):
			return False
		return True

	# query ⊆ value  OR  value ⊆ query
	return (
		_contains(q_text, q_urls, v_text, v_urls)
		or _contains(v_text, v_urls, q_text, q_urls)
	)

def _reverse_scan(db_manager: DatabaseManager, query_text: str) -> list[tuple[float, Union[int, str], str, str]]:
	"""
	Scans every saved value and returns entries whose content contains the
	query (or is contained by the query) at the segment level.
	Score reflects coverage: exact matches score 1.0, containment is weighted
	by how much of the longer string the shorter covers.
	"""
	q = clean_value(query_text)
	if not q:
		return []

	len_q = len(q)
	results: list[tuple[float, Union[int, str], str, str]] = []
	for uid, user_db in db_manager.get_all_users().items():
		for key, value in user_db.items():
			v = clean_value(value)
			if not v:
				continue

			if v == q:
				results.append((1.0, uid, key, value))
				continue

			if _segments_match(q, v):
				# Score by coverage so tighter matches rank higher
				coverage = min(len_q, len(v)) / max(len_q, len(v))
				score = 0.75 + 0.24 * coverage
				results.append((score, uid, key, value))

	results.sort(key=lambda r: r[0], reverse=True)
	return results

async def handle_revsearch(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None,
	message: Optional[discord.Message] = None
) -> discord.Embed:
	"""
	Admin-only reverse search: reply to ANY message to find saved keys whose
	values contain (or are contained by) that message's content.
	"""
	if not is_admin(user.id):
		return error_embed("You don't have permission to use this command.")

	resolved = getattr(reply, 'resolved', None) if reply else None
	if resolved is None:
		return error_embed("Usage: Reply to any message with `;;revsearch`")

	query_text = (getattr(resolved, 'content', '') or '').strip()
	if not query_text:
		attachment_text = get_attachments_text(resolved).strip()
		if attachment_text:
			query_text = attachment_text
		else:
			return error_embed("The replied message has no text or media content to search for.")

	# Offload the full-DB scan to a worker thread to keep the event loop unblocked
	results = await asyncio.to_thread(_reverse_scan, db_manager, query_text)

	if not results:
		return info_embed("No saved keys match that message's content.")

	lines = []
	for score, uid, key, value in results[:REVSEARCH_MAX_RESULTS]:
		preview = value.replace('\n', ' ')
		if len(preview) > 60:
			preview = preview[:57] + '...'
		match_label = 'exact' if score >= 0.999 else f'{round(score * 100)}%'
		lines.append(f"- `;;{key};;` — <@{uid}> *({match_label})*\n  > {preview}")

	embed = discord.Embed(
		title="🔎 Reverse Search Results",
		description="\n".join(lines),
		color=discord.Color.blurple()
	)
	footer = f"{len(results)} match(es) found"
	if len(results) > REVSEARCH_MAX_RESULTS:
		footer += f" • showing top {REVSEARCH_MAX_RESULTS}"
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
