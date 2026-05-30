from sqlitedict import SqliteDict
import discord
import constants

def gsearch(db: SqliteDict, search_key: str) -> discord.Embed:
	"""Search through all users' keys for matches. Returns results grouped by user in an embed."""
	sections = []

	for user_id in db.keys():
		user_db = db.get(user_id, {})
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
