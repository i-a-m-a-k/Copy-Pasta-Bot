from typing import Optional
import re
import asyncio
from collections import defaultdict
import discord
import constants
from core.config import extract_user_id
from core.database import DatabaseManager
from ui.embeds import error_embed, info_embed

# Regex to strip ephemeral query parameters from Discord CDN attachments
DISCORD_CDN_PARAMS_RE = re.compile(r'(\.(?:png|jpg|jpeg|gif|webp|mp4|mov))\?[^\s\)]+', re.IGNORECASE)

def clean_value(v: str) -> str:
	"""
	Normalizes a key's value for comparison:
	- Strips leading/trailing whitespace
	- Lowercases the content
	- Strips ephemeral Discord CDN tokens (?ex=...&is=...&hm=...)
	"""
	if not isinstance(v, str):
		return ""
	cleaned = v.strip().lower()
	cleaned = DISCORD_CDN_PARAMS_RE.sub(r'\1', cleaned)
	return cleaned

def compute_fast_similarity(v1: str, v2: str) -> float:
	"""
	Ultra-fast O(L) similarity score without quadratic difflib overhead.
	Uses word-level Jaccard for multi-word texts and character 3-grams for short strings/links.
	"""
	if v1 == v2:
		return 1.0
	len1, len2 = len(v1), len(v2)
	if len1 == 0 or len2 == 0:
		return 0.0

	# Fast length ratio check: if lengths differ by more than 20%, similarity cannot reach cutoff
	if min(len1, len2) / max(len1, len2) < 0.80:
		return 0.0

	# 1. Word-level Jaccard for multi-word texts
	words1 = set(v1.split())
	words2 = set(v2.split())
	if len(words1) >= 4 and len(words2) >= 4:
		union = len(words1 | words2)
		if union == 0:
			return 0.0
		return len(words1 & words2) / union

	# 2. Character 3-gram Jaccard for short strings or URLs
	n = 3
	if len1 < n or len2 < n:
		return 1.0 if v1 == v2 else 0.0

	grams1 = {v1[i:i+n] for i in range(len1 - n + 1)}
	grams2 = {v2[i:i+n] for i in range(len2 - n + 1)}
	union = len(grams1 | grams2)
	if union == 0:
		return 0.0
	return len(grams1 & grams2) / union

def render_vibe_bar(pct: float, total_blocks: int = 10) -> str:
	"""Generates a visual progress bar representing vibe match percentage."""
	filled = int(round((pct / 100.0) * total_blocks))
	filled = max(0, min(total_blocks, filled))
	return "▰" * filled + "▱" * (total_blocks - filled)

def calculate_value_vibe_score(
	user_a_vals: set[str],
	user_b_vals: set[str],
	similarity_cutoff: float = 0.82
) -> tuple[float, int, int]:
	"""
	Calculates vibe percentage similarity strictly based on KEY VALUES (no key names).
	
	Performance Strategy:
	1. Exact normalized matches: O(N) hash set intersection (< 0.1ms).
	2. Unmatched candidates: Length-bucketed indexing with fast O(L) token Jaccard similarity.
	
	Returns:
		tuple: (percentage, num_exact_matches, num_fuzzy_matches)
	"""
	len_a = len(user_a_vals)
	len_b = len(user_b_vals)

	if len_a == 0 or len_b == 0:
		return 0.0, 0, 0

	# 1. Exact matches between normalized values (O(N) in C)
	exact_matches = user_a_vals & user_b_vals
	num_exact = len(exact_matches)

	# 2. Unmatched values candidate pools
	unmatched_a = list(user_a_vals - exact_matches)
	unmatched_b = list(user_b_vals - exact_matches)

	fuzzy_matches = 0
	if unmatched_a and unmatched_b:
		# Length bucket indexing for O(1) candidate lookup
		bucket_size = 25
		b_buckets = defaultdict(list)
		for j, b_val in enumerate(unmatched_b):
			b_buckets[len(b_val) // bucket_size].append((j, b_val))

		used_b_indices = set()

		for val_a in unmatched_a:
			len_a_val = len(val_a)
			b_bin = len_a_val // bucket_size
			best_score = 0.0
			best_j = -1

			# Only check adjacent length buckets (within +/- 1 bucket)
			candidates = []
			for bin_idx in (b_bin - 1, b_bin, b_bin + 1):
				candidates.extend(b_buckets.get(bin_idx, []))

			for j, val_b in candidates:
				if j in used_b_indices:
					continue
				score = compute_fast_similarity(val_a, val_b)
				if score >= similarity_cutoff and score > best_score:
					best_score = score
					best_j = j
					if score >= 0.95:
						break

			if best_j != -1:
				used_b_indices.add(best_j)
				fuzzy_matches += 1

	total_matched = num_exact + fuzzy_matches
	if total_matched == 0:
		return 0.0, 0, 0

	# 4. Blended similarity: Overlap Coefficient (60%) + Sørensen-Dice Index (40%)
	overlap = total_matched / min(len_a, len_b)
	dice = (2.0 * total_matched) / (len_a + len_b)
	raw_score = overlap * 0.6 + dice * 0.4

	# 5. Heavy optimistic curve scaling:
	# 50% raw match or above qualifies as Soulmates (>= 90.0%).
	# For raw_score < 0.50, sublinear power scaling ((raw_score / 0.50)^0.35 * 90.0) lifts
	# small overlaps (4-5% -> 37-40%, 10% -> 51%, 25% -> 71%) while keeping 0 matches strictly at 0.0%.
	if raw_score >= 0.50:
		scaled = 90.0 + min(10.0, ((raw_score - 0.50) / 0.50) * 10.0)
	else:
		ratio = max(0.0, raw_score / 0.50)
		scaled = (ratio ** 0.35) * 90.0

	pct = round(max(0.0, min(100.0, scaled)), 1)
	return pct, num_exact, fuzzy_matches

def get_vibe_tier(pct: float) -> tuple[str, str, discord.Color]:
	"""Returns tier title, flavor quote, and Discord embed color for a given percentage."""
	if pct >= 90.0:
		return (
			"💍 Soulmates",
			"You two share the exact same braincell! Peak copypasta compatibility.",
			discord.Color.purple()
		)
	elif pct >= 70.0:
		return (
			"🔥 Twin Flames",
			"Incredible chemistry! Your memes and pastas are on the exact same wavelength.",
			discord.Color.red()
		)
	elif pct >= 50.0:
		return (
			"✨ Great Vibe",
			"Strong mutual taste! You both save and share a lot of the same pastas.",
			discord.Color.gold()
		)
	elif pct >= 25.0:
		return (
			"🤝 Casual Homies",
			"Decent overlap! You share some common memes, with plenty of room to swap more.",
			discord.Color.green()
		)
	elif pct >= 1.0:
		return (
			"🧊 Acquaintances",
			"A slight hint of common ground, but you mostly operate on different wavelengths.",
			discord.Color.blue()
		)
	else:
		return (
			"🚫 Polar Opposites",
			"Zero in common! You two come from completely different meme universes.",
			discord.Color.dark_grey()
		)

async def handle_vibematch(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None
) -> discord.Embed:
	"""
	Compares saved key collections between two users:
	Supports:
	- `;;vibematch @user1 @user2`: compares user 1 and user 2
	- `;;vibematch @user`: compares invoking user with target user
	- `;;vibematch` (reply): compares invoking user with message author
	"""
	user1_id: Optional[int] = None
	user2_id: Optional[int] = None

	if len(args) >= 3:
		# Multi-target: ;;vibematch @user1 @user2
		u1 = extract_user_id(args[1])
		u2 = extract_user_id(args[2])
		if u1 is None:
			return error_embed(f"Could not identify the first user: `{args[1]}`. Usage: `;;vibematch @user1 @user2`")
		if u2 is None:
			return error_embed(f"Could not identify the second user: `{args[2]}`. Usage: `;;vibematch @user1 @user2`")
		user1_id = u1
		user2_id = u2
	elif len(args) == 2:
		# Single target: ;;vibematch @user
		target = extract_user_id(args[1])
		if target is None:
			return error_embed(f"Could not identify user: `{args[1]}`. Usage: `;;vibematch @user` or `;;vibematch @user1 @user2`")
		user1_id = user.id
		user2_id = target
	elif reply and reply.resolved and hasattr(reply.resolved, 'author'):
		# Reply fallback: ;;vibematch
		user1_id = user.id
		user2_id = reply.resolved.author.id
	else:
		return error_embed(
			"Please mention a user or reply to their message:\n"
			"• `;;vibematch @user`\n"
			"• `;;vibematch @user1 @user2`"
		)

	# Handle self-matching
	if user1_id == user2_id:
		if user1_id == user.id:
			return info_embed(
				"You matched **100.0%** with yourself! 💕\nTrue self-love, but try matching with someone else!",
				title="🔮 Vibe Match: 100%"
			)
		else:
			return info_embed(
				f"<@{user1_id}> matched **100.0%** with themselves! 💕\nTry comparing two different users.",
				title="🔮 Vibe Match: 100%"
			)

	_, user1_db = db_manager._get_user_entry(user1_id)
	_, user2_db = db_manager._get_user_entry(user2_id)

	if not user1_db and not user2_db:
		return info_embed(f"Neither <@{user1_id}> nor <@{user2_id}> have saved any keys yet!")

	if not user1_db:
		msg = "You haven't saved any keys yet! Save some keys using `;;add` before checking your vibe." if user1_id == user.id else f"<@{user1_id}> hasn't saved any keys yet!"
		return info_embed(msg)

	if not user2_db:
		msg = "You haven't saved any keys yet! Save some keys using `;;add` before checking your vibe." if user2_id == user.id else f"<@{user2_id}> hasn't saved any keys yet!"
		return info_embed(msg)

	# Extract unique cleaned values for calculation (key names NOT used in calculation)
	user1_val_set = {clean_value(v) for v in user1_db.values() if clean_value(v)}
	user2_val_set = {clean_value(v) for v in user2_db.values() if clean_value(v)}

	# Offload calculation to a background worker thread to ensure the event loop is 100% unblocked
	pct, num_exact, num_fuzzy = await asyncio.to_thread(
		calculate_value_vibe_score,
		user1_val_set,
		user2_val_set
	)
	total_matched_vals = num_exact + num_fuzzy

	# Map lowercase to original key display names
	user1_map = {k.lower(): k for k in user1_db.keys()}
	user2_map = {k.lower(): k for k in user2_db.keys()}
	common_key_lowers = sorted(set(user1_map.keys()) & set(user2_map.keys()))

	# Find keys that share BOTH the same key name and the same key value
	def get_shared_identical() -> list[str]:
		shared: list[str] = []
		for k_lower in common_key_lowers:
			k1_orig = user1_map[k_lower]
			k2_orig = user2_map[k_lower]
			v1 = clean_value(user1_db[k1_orig])
			v2 = clean_value(user2_db[k2_orig])
			if v1 and (v1 == v2 or compute_fast_similarity(v1, v2) >= 0.90):
				shared.append(k1_orig)
		return shared

	shared_identical_keys = await asyncio.to_thread(get_shared_identical)

	tier_title, tier_quote, tier_color = get_vibe_tier(pct)
	bar = render_vibe_bar(pct)

	embed = discord.Embed(
		title="🔮 Vibe Match Compatibility",
		color=tier_color
	)

	embed.description = (
		f"### <@{user1_id}> + <@{user2_id}>\n"
		f"**{tier_title}** — `{pct}%`\n"
		f"`{bar}`\n\n"
		f"*{tier_quote}*"
	)

	embed.add_field(
		name="📊 Collection Size",
		value=(
			f"• <@{user1_id}>: **{len(user1_db)}** key(s)\n"
			f"• <@{user2_id}>: **{len(user2_db)}** key(s)"
		),
		inline=True
	)

	embed.add_field(
		name="🔑 Similarities",
		value=(
			f"• Matched Values: **{total_matched_vals}**\n"
			f"• Identical Keys: **{len(shared_identical_keys)}**"
		),
		inline=True
	)

	# Shared keys section: ONLY show if keys share BOTH the same key name and same value.
	# If there are none, do NOT show this section at all.
	if shared_identical_keys:
		sample_keys = [f"`;;{k};;`" for k in shared_identical_keys[:12]]
		keys_text = " • ".join(sample_keys)
		if len(shared_identical_keys) > 12:
			keys_text += f"\n*...and {len(shared_identical_keys) - 12} more*"
		embed.add_field(
			name=f"📜 Shared Keys ({len(shared_identical_keys)})",
			value=keys_text,
			inline=False
		)

	embed.set_footer(text="Tip: Use ;;steal @user <key> to borrow their best keys!")
	return embed
