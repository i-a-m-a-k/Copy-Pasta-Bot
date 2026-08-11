from typing import Iterable
import discord
from core.config import is_admin, disabled_commands, save_disabled_commands
from ui.embeds import success_embed, error_embed, warning_embed, info_embed

def handle_disable(
	user: discord.User,
	args: list[str],
	message: discord.Message,
	available_commands: Iterable[str]
) -> discord.Embed:
	"""Disables a specific command for the current guild (Admins / Manage Guild only)."""
	member = message.guild.get_member(user.id) if message.guild else None
	has_server_perms = member and (member.guild_permissions.manage_guild or member.guild_permissions.administrator)
	if not is_admin(user.id) and not has_server_perms:
		return error_embed("You don't have permission to use this command.")

	if len(args) != 2:
		return error_embed("Usage: `;;disable <command>` (e.g. `;;disable dream`)")

	cmd_to_disable = args[1].lower()
	if cmd_to_disable not in available_commands or cmd_to_disable in ['disable', 'enable']:
		return error_embed(f"Cannot disable `{cmd_to_disable}`.")

	guild_id = str(message.guild.id)
	if guild_id not in disabled_commands:
		disabled_commands[guild_id] = []

	if cmd_to_disable in disabled_commands[guild_id]:
		return warning_embed(f"`{cmd_to_disable}` is already disabled in this server.")

	disabled_commands[guild_id].append(cmd_to_disable)
	save_disabled_commands()
	return warning_embed(f"Command `{cmd_to_disable}` has been disabled in this server.", title="🔒 Command Disabled")

def handle_enable(
	user: discord.User,
	args: list[str],
	message: discord.Message
) -> discord.Embed:
	"""Re-enables a disabled command for the current guild (Admins / Manage Guild only)."""
	member = message.guild.get_member(user.id) if message.guild else None
	has_server_perms = member and (member.guild_permissions.manage_guild or member.guild_permissions.administrator)
	if not is_admin(user.id) and not has_server_perms:
		return error_embed("You don't have permission to use this command.")

	if len(args) != 2:
		return error_embed("Usage: `;;enable <command>` (e.g. `;;enable dream`)")

	cmd_to_enable = args[1].lower()
	guild_id = str(message.guild.id)

	if guild_id not in disabled_commands or cmd_to_enable not in disabled_commands[guild_id]:
		return info_embed(f"`{cmd_to_enable}` is not currently disabled in this server.")

	disabled_commands[guild_id].remove(cmd_to_enable)
	save_disabled_commands()
	return success_embed(f"Command `{cmd_to_enable}` has been re-enabled in this server.", title="🔓 Command Enabled")
