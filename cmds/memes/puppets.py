from typing import Callable, Union, Optional
import discord
from ui.embeds import warning_embed
from . import flirt
from . import roast

def handle_flirt(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference],
	message: discord.Message
) -> Union[dict, discord.Embed]:
	"""Handles the ;;flirt puppet command."""
	if len(message.mentions) == 0:
		return warning_embed("You need to mention someone to flirt with! Try `;;flirt @username`")
	flirt_text = flirt.handle_flirt_command(message)

	return {
		"type": "puppet",
		"content": flirt_text,
		"author": user,
		"target_channel": message.channel
	}

def handle_roast(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference],
	message: discord.Message,
	get_bot: Callable[[], discord.ClientUser]
) -> dict:
	"""Handles the ;;roast puppet command."""
	roast_text = roast.handle_roast(message, get_bot())

	return {
		"type": "puppet",
		"content": roast_text,
		"author": user,
		"target_channel": message.channel
	}
