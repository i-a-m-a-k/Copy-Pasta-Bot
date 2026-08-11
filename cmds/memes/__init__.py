from typing import Union, Optional
import discord
from ui.embeds import warning_embed

from .transforms import create_transform_handler
from .puppets import handle_flirt, handle_roast
from . import mock
from . import deepfry
from . import dream
from . import regexc

def handle_mock(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference]
) -> Union[discord.Embed, discord.File]:
	"""Handles the ;;mock SpongeBob text overlay command."""
	if reply is None or reply.resolved is None:
		return warning_embed("You need to reply to a message to use this command.")
	result = mock.handle_mock_command(reply)
	if result is None:
		return warning_embed("The message you replied to contains no text to mock.", title="⚠️ No Text Found")
	return result

async def handle_deepfry(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference],
	message: Optional[discord.Message] = None
) -> Union[discord.Embed, discord.File]:
	"""Handles the ;;deepfry command with ML iris eye flares."""
	if reply is None and (message is None or not message.attachments):
		return warning_embed("You need to reply to a message with an image or attach one to use this command.")
	return await deepfry.handle_deepfry_command(reply, message)

async def handle_dream(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference]
) -> Union[str, discord.File, discord.Embed, None]:
	"""Handles the ;;dream Luma AI image and video generation command."""
	return await dream.handle_dream_command(user, args, message=reply)

__all__ = [
	'create_transform_handler',
	'handle_flirt',
	'handle_roast',
	'handle_mock',
	'handle_deepfry',
	'handle_dream',
	'regexc',
]
