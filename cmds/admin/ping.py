import asyncio
from datetime import datetime, timezone
import math
from typing import Callable, Optional
import discord
from core.config import is_admin
from ui.embeds import error_embed


async def handle_ping(
	user: discord.User,
	message: Optional[discord.Message] = None,
	get_client: Optional[Callable[[], Optional[discord.Client]]] = None
) -> discord.Embed:
	"""
	Admin-only command to check bot responsiveness.
	Returns an embed displaying Turnaround Time (TAT), Discord Gateway latency,
	and Asyncio event loop scheduling lag.
	"""
	if not is_admin(user.id):
		return error_embed("You don't have permission to use this command.", title="🔒 Admin Only")

	now = datetime.now(timezone.utc)
	if message and hasattr(message, 'created_at') and message.created_at:
		tat_ms = max(1, round((now - message.created_at).total_seconds() * 1000))
	else:
		tat_ms = 0

	# Measure asyncio event loop scheduling lag
	loop = asyncio.get_running_loop()
	t0 = loop.time()
	await asyncio.sleep(0)
	loop_lag_ms = max(0.0, (loop.time() - t0) * 1000)

	api_ms: Optional[int] = None
	if get_client:
		try:
			client = get_client()
			if client and hasattr(client, 'latency') and client.latency is not None:
				if not math.isnan(client.latency) and not math.isinf(client.latency):
					api_ms = round(client.latency * 1000)
		except Exception:
			pass

	embed = discord.Embed(
		title="🏓 Pong!",
		color=discord.Color.green(),
		timestamp=now
	)
	embed.add_field(name="⏱️ Turnaround Time (TAT)", value=f"`{tat_ms} ms`", inline=True)
	if api_ms is not None:
		embed.add_field(name="🌐 API / Gateway", value=f"`{api_ms} ms`", inline=True)
	embed.add_field(name="⚡ Event Loop Latency", value=f"`{loop_lag_ms:.2f} ms`", inline=True)
	embed.set_footer(text="Admin Diagnostic • Auto-deletes in 60s")

	return embed
