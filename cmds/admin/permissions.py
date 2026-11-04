from typing import Iterable
import discord
from core.config import (
	is_admin,
	disabled_commands,
	save_disabled_commands,
	is_command_disabled_globally,
	GLOBAL_GUILD_KEY,
)
from ui.embeds import success_embed, error_embed, warning_embed, info_embed

PROTECTED_COMMANDS = {'disable', 'enable'}

def _has_mod_perms(member: discord.Member) -> bool:
	"""Check if a member has moderator-level permissions in the guild."""
	perms = member.guild_permissions
	return perms.manage_guild or perms.administrator or perms.manage_messages

def _is_global_flag(arg: str) -> bool:
	return arg.lower() in ('--global', '-g')

def handle_disable(
	user: discord.User,
	args: list[str],
	message: discord.Message,
	available_commands: Iterable[str]
) -> discord.Embed:
	"""Disables a command for the current guild, or globally with --global (bot admins only)."""
	# --- Permission check ---
	member = message.guild.get_member(user.id) if message.guild else None
	has_server_perms = member and _has_mod_perms(member)
	bot_admin = is_admin(user.id)
	if not bot_admin and not has_server_perms:
		return error_embed("You don't have permission to use this command.")

	# --- Arg parsing: extract command name and optional --global flag ---
	if len(args) < 2:
		return error_embed(
			"Usage: `;;disable <command>` or `;;disable <command> --global`\n"
			"(e.g. `;;disable dream` or `;;disable dream -g`)"
		)

	cmd_to_disable = args[1].lower()
	is_global = any(_is_global_flag(a) for a in args[2:])

	# --- Validate command ---
	if cmd_to_disable not in available_commands or cmd_to_disable in PROTECTED_COMMANDS:
		return error_embed(f"Cannot disable `{cmd_to_disable}`.")

	# --- Global disable (bot admins only) ---
	if is_global:
		if not bot_admin:
			return error_embed("Only bot admins can disable commands globally.")

		if GLOBAL_GUILD_KEY not in disabled_commands:
			disabled_commands[GLOBAL_GUILD_KEY] = []

		if cmd_to_disable in disabled_commands[GLOBAL_GUILD_KEY]:
			return warning_embed(f"`{cmd_to_disable}` is already globally disabled.")

		disabled_commands[GLOBAL_GUILD_KEY].append(cmd_to_disable)
		save_disabled_commands()
		return warning_embed(
			f"Command `{cmd_to_disable}` has been **globally disabled** across all servers and DMs.",
			title="🌐 Globally Disabled"
		)

	# --- Per-guild disable ---
	if not message.guild:
		return error_embed("This command can only be used in a server. Use `--global` to disable globally.")

	guild_id = str(message.guild.id)
	if guild_id not in disabled_commands:
		disabled_commands[guild_id] = []

	if cmd_to_disable in disabled_commands[guild_id]:
		return warning_embed(f"`{cmd_to_disable}` is already disabled in this server.")

	# Prevent per-guild disable if already globally disabled
	if is_command_disabled_globally(cmd_to_disable):
		return info_embed(f"`{cmd_to_disable}` is already globally disabled by the bot owner.")

	disabled_commands[guild_id].append(cmd_to_disable)
	save_disabled_commands()
	return warning_embed(f"Command `{cmd_to_disable}` has been disabled in this server.", title="🔒 Command Disabled")

def handle_enable(
	user: discord.User,
	args: list[str],
	message: discord.Message
) -> discord.Embed:
	"""Re-enables a disabled command for the current guild, or globally with --global (bot admins only)."""
	# --- Permission check ---
	member = message.guild.get_member(user.id) if message.guild else None
	has_server_perms = member and _has_mod_perms(member)
	bot_admin = is_admin(user.id)
	if not bot_admin and not has_server_perms:
		return error_embed("You don't have permission to use this command.")

	# --- Arg parsing: extract command name and optional --global flag ---
	if len(args) < 2:
		return error_embed(
			"Usage: `;;enable <command>` or `;;enable <command> --global`\n"
			"(e.g. `;;enable dream` or `;;enable dream -g`)"
		)

	cmd_to_enable = args[1].lower()
	is_global = any(_is_global_flag(a) for a in args[2:])

	# --- Global enable (bot admins only) ---
	if is_global:
		if not bot_admin:
			return error_embed("Only bot admins can enable commands globally.")

		if GLOBAL_GUILD_KEY not in disabled_commands or cmd_to_enable not in disabled_commands[GLOBAL_GUILD_KEY]:
			return info_embed(f"`{cmd_to_enable}` is not currently globally disabled.")

		disabled_commands[GLOBAL_GUILD_KEY].remove(cmd_to_enable)
		save_disabled_commands()
		return success_embed(
			f"Command `{cmd_to_enable}` has been **globally re-enabled** across all servers and DMs.",
			title="🌐 Globally Enabled"
		)

	# --- Per-guild enable ---
	if not message.guild:
		return error_embed("This command can only be used in a server. Use `--global` to enable globally.")

	# Prevent per-guild enable if globally disabled
	if is_command_disabled_globally(cmd_to_enable):
		return info_embed(f"`{cmd_to_enable}` is globally disabled by the bot owner and cannot be enabled per-server.")

	guild_id = str(message.guild.id)

	if guild_id not in disabled_commands or cmd_to_enable not in disabled_commands[guild_id]:
		return info_embed(f"`{cmd_to_enable}` is not currently disabled in this server.")

	disabled_commands[guild_id].remove(cmd_to_enable)
	save_disabled_commands()
	return success_embed(f"Command `{cmd_to_enable}` has been re-enabled in this server.", title="🔓 Command Enabled")
