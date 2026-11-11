from typing import Callable, Optional, Union
import inspect
import discord
import constants
from core.database import DatabaseManager
from core.config import is_command_disabled, is_command_disabled_globally, is_admin
from core.cooldown import CooldownManager
from ui.embeds import warning_embed

from . import copypasta as cp
from . import memes as mm
from . import admin as adm
from . import help as hp

class CommandHandler:
	"""
	Central command router for CopyPastaBot.
	Maps command strings to modular handlers across copypasta, memes, and admin subpackages.
	"""
	def __init__(
		self,
		db_manager: DatabaseManager,
		get_bot: Callable[[], discord.ClientUser],
		get_client: Optional[Callable[[], Optional[discord.Client]]] = None
	):
		self.db = db_manager
		self.get_bot = get_bot
		self.get_client = get_client
		self.cooldown_manager = CooldownManager(
			default_cooldown=constants.DEFAULT_COOLDOWN,
			dream_cooldown=constants.DREAM_COOLDOWN
		)

		self.commands = {
			# --- Copypasta Commands ---
			'add': lambda u, a, r, m: cp.handle_add(self.db, u, a, r, m, overwrite=False),
			'add_o': lambda u, a, r, m: cp.handle_add(self.db, u, a, r, m, overwrite=True),
			'saved': lambda u, a, r, m: cp.handle_saved(self.db, u, a, m),
			'delete': lambda u, a, r, m: cp.handle_delete(self.db, u, a, r),
			'delete_me': lambda u, a, r, m: cp.handle_delete_me(self.db, u, a, r),
			'rename': lambda u, a, r, m: cp.handle_rename(self.db, u, a, overwrite=False),
			'rename_o': lambda u, a, r, m: cp.handle_rename(self.db, u, a, overwrite=True),
			'steal': lambda u, a, r, m: cp.handle_steal(self.db, u, a, r),
			'delkey': lambda u, a, r, m: cp.handle_delkey(self.db, u, a, r, m, self.get_bot),
			'random': lambda u, a, r, m: cp.handle_random(self.db, u, a),
			'grandom': lambda u, a, r, m: cp.handle_grandom(self.db, u, a),
			'search': lambda u, a, r, m: cp.handle_search(self.db, u, a),
			'gsearch': lambda u, a, r, m: cp.handle_gsearch(self.db, u, a),
			'export': lambda u, a, r, m: cp.handle_export(self.db, u, a, r, m),
			'import': lambda u, a, r, m: cp.handle_import(self.db, u, a, r, m),
			'vibematch': lambda u, a, r, m: cp.handle_vibematch(self.db, u, a, r),
			'revsearch': lambda u, a, r, m: cp.handle_revsearch(self.db, u, a, r, m),

			# --- Meme & Media Commands ---
			'clap': mm.create_transform_handler('clap'),
			'zalgo': mm.create_transform_handler('zalgo'),
			'copypasta': mm.create_transform_handler('copypasta'),
			'owo': mm.create_transform_handler('owo'),
			'stretch': mm.create_transform_handler('stretch'),
			'vaporwave': mm.create_transform_handler('vaporwave'),
			'emojify': mm.create_transform_handler('emojify'),
			'mock': lambda u, a, r, m: mm.handle_mock(u, a, r, m),
			'deepfry': lambda u, a, r, m: mm.handle_deepfry(u, a, r, m),
			'dream': lambda u, a, r, m: mm.handle_dream(u, a, r, m, self.get_client),
			'roast': lambda u, a, r, m: mm.handle_roast(u, a, r, m, self.get_bot),
			'flirt': lambda u, a, r, m: mm.handle_flirt(u, a, r, m),
			'thonkify': lambda u, a, r, m: mm.handle_thonkify_command(u, a, r, m),
			'dadjoke': lambda u, a, r, m: mm.handle_dadjoke(u, a, r, m),
			'cat': lambda u, a, r, m: mm.handle_cat(u, a, r, m),
			'lmgtfy': lambda u, a, r, m: mm.handle_lmgtfy(u, a, r, m),
			'tr': lambda u, a, r, m: mm.handle_translate(u, a, r, m),
			's': lambda u, a, r, m: mm.regexc.handle_regex(a, r),

			# --- Admin & Permissions ---
			'disable': lambda u, a, r, m: adm.handle_disable(u, a, m, self.commands.keys()),
			'enable': lambda u, a, r, m: adm.handle_enable(u, a, m),
			'blacklist_add': lambda u, a, r, m: adm.handle_blacklist_add(u, a, r),
			'blacklist_remove': lambda u, a, r, m: adm.handle_blacklist_remove(u, a, r),
			'ping': lambda u, a, r, m: adm.handle_ping(u, m, self.get_client),
			'starboard': lambda u, a, r, m: adm.handle_starboard(u, a, m),

			# --- Help ---
			'help': lambda u, a, r, m: hp.handle_help(a),
		}

	async def handle_command(
		self,
		user: discord.User,
		cmd: str,
		reply: Optional[discord.MessageReference] = None,
		message: Optional[discord.Message] = None
	) -> Optional[Union[str, discord.File, discord.Embed, dict]]:
		"""Parses and executes a command string, checking per-guild permission states."""
		if not cmd.startswith(';;') or len(cmd) <= 2 or cmd[2].isspace():
			return None

		cmd = cmd[2:]

		args = cmd.split()
		if not args:
			return None

		command = args[0]
		if command in self.commands:
			# Disabled command checks (bot admins bypass all restrictions)
			if not is_admin(user.id):
				# Global disable check: applies everywhere (guilds AND DMs)
				if is_command_disabled_globally(command):
					return warning_embed(f"Command `{command}` is globally disabled by the bot owner.", title="🔒 Globally Disabled")

				# Per-guild disable check: only applies in guilds
				if message and hasattr(message, 'guild') and message.guild:
					if is_command_disabled(message.guild.id, command):
						return warning_embed(f"Command `{command}` is disabled in this server.", title="🔒 Command Disabled")

			# Cooldown enforcement (exempt bot admins)
			if not is_admin(user.id):
				cd_status = self.cooldown_manager.check(user.id, command)
				if cd_status is not None:
					time_remaining, expires_timestamp, should_warn = cd_status
					if should_warn:
						return {
							"embed": warning_embed(
								f"You're on cooldown for `;;{command}`. You can use it again <t:{expires_timestamp}:R>.",
								title="⏳ Cooldown Active"
							),
							"delete_after": max(1.0, time_remaining)
						}
					# Spam suppression: silently ignore further messages while on cooldown
					return None

				# Not on cooldown; start cooldown window for this command
				self.cooldown_manager.trigger(user.id, command)

			handler = self.commands[command]
			result = handler(user, args, reply, message)
			if inspect.isawaitable(result):
				return await result
			return result

		return None

__all__ = ['CommandHandler']
