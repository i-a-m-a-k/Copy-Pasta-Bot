import re
from types import SimpleNamespace
from typing import Union
import discord
import constants
from ui.embeds import warning_embed

CHAIN_SPLIT_REGEX = re.compile(r'\s*\|\s*(?=;;)')

def split_chain(content: str) -> list[str]:
	"""Splits a message into chain stages on pipes that are followed by `;;`."""
	return CHAIN_SPLIT_REGEX.split(content.strip())

def parse_chain(content: str) -> Union[list[list[str]], discord.Embed]:
	"""Validates a chain and returns each stage's args, or a warning embed."""
	stages = split_chain(content)
	if len(stages) > constants.MAX_CHAIN_DEPTH:
		return warning_embed(
			f"Chains are limited to {constants.MAX_CHAIN_DEPTH} commands.",
			title="⛓️ Chain Too Long"
		)

	parsed = []
	for index, stage in enumerate(stages, 1):
		args = stage[2:].split()
		if not args:
			return warning_embed(f"Stage {index} of the chain is empty.", title="⛓️ Invalid Chain")

		command = args[0]
		if command in constants.CHAIN_FINAL_COMMANDS:
			if index != len(stages):
				return warning_embed(
					f"`{command}` produces an image and can only be the last command in a chain.",
					title="⛓️ Invalid Chain"
				)
			if len(args) > 1:
				return warning_embed(
					f"`{command}` takes no text in a chain; it uses the previous command's output.",
					title="⛓️ Invalid Chain"
				)
		elif command not in constants.CHAIN_TEXT_COMMANDS:
			return warning_embed(f"`{command}` cannot be used in a chain.", title="⛓️ Invalid Chain")

		parsed.append(args)
	return parsed

def as_reply(content: str, source: discord.Message) -> SimpleNamespace:
	"""Wraps intermediate text so handlers can read it like a replied-to message."""
	return SimpleNamespace(
		resolved=SimpleNamespace(content=content, mentions=getattr(source, 'mentions', []))
	)

def stage_error(index: int, command: str, embed: discord.Embed) -> discord.Embed:
	"""Prefixes a handler's error embed with the failing stage."""
	embed.description = f"Stage {index} (`{command}`): {embed.description or ''}"
	return embed

__all__ = ['split_chain', 'parse_chain', 'as_reply', 'stage_error']
