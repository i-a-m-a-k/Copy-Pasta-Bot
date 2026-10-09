import random
from typing import Optional, Union
import aiohttp
import discord

from ui.embeds import error_embed, warning_embed
from ui.helpers import get_http_session

DADJOKE_BASE_URL = "https://icanhazdadjoke.com"
DADJOKE_USER_AGENT = "CopyPastaBot Discord"
DADJOKE_TIMEOUT = aiohttp.ClientTimeout(total=10)


async def fetch_dadjoke_text(
	query: Optional[str] = None
) -> tuple[Optional[str], Optional[discord.Embed]]:
	"""
	Fetches a dad joke string from icanhazdadjoke.com using the custom User-Agent.
	Returns (joke_text, error_embed).
	"""
	session = await get_http_session()
	headers = {
		"User-Agent": DADJOKE_USER_AGENT,
		"Accept": "application/json"
	}

	if query:
		search_url = f"{DADJOKE_BASE_URL}/search"
		params = {"term": query}
		async with session.get(search_url, params=params, headers=headers, timeout=DADJOKE_TIMEOUT) as resp:
			if resp.status != 200:
				return None, error_embed(
					f"Failed to search dad jokes (HTTP {resp.status}).",
					title="❌ API Error"
				)
			data = await resp.json(content_type=None)
			results = data.get("results", [])
			if not results:
				return None, warning_embed(
					f'No dad jokes found matching "{query}".',
					title="⚠️ No Jokes Found"
				)
			chosen = random.choice(results)
			joke_text = chosen.get("joke")
	else:
		async with session.get(f"{DADJOKE_BASE_URL}/", headers=headers, timeout=DADJOKE_TIMEOUT) as resp:
			if resp.status != 200:
				return None, error_embed(
					f"Failed to fetch a dad joke (HTTP {resp.status}).",
					title="❌ API Error"
				)
			data = await resp.json(content_type=None)
			joke_text = data.get("joke")

	if not joke_text:
		return None, error_embed("Received invalid response from dad joke API.", title="❌ Invalid Response")

	return joke_text.strip(), None


async def handle_dadjoke(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None,
	message: Optional[discord.Message] = None
) -> Union[str, discord.Embed]:
	"""
	Handles the ;;dadjoke command.
	Fetches a random or topic-searched dad joke text from icanhazdadjoke.com.
	"""
	query = ' '.join(args[1:]).strip() if len(args) > 1 else None

	try:
		joke_text, err_embed = await fetch_dadjoke_text(query)
		if err_embed:
			return err_embed
		if not joke_text:
			return error_embed("An unexpected error occurred while fetching the dad joke.", title="❌ Error")

		return joke_text

	except aiohttp.ClientError as e:
		return error_embed(f"Network error communicating with dad joke API: {e}", title="🌐 Network Error")
	except Exception as e:
		return error_embed(f"Failed to fetch dad joke: {e}", title="❌ Error")
