from typing import Optional
import discord

def success_embed(description: str, title: Optional[str] = None) -> discord.Embed:
	embed = discord.Embed(description=description, color=discord.Color.green())
	if title:
		embed.title = title
	return embed

def error_embed(description: str, title: Optional[str] = None) -> discord.Embed:
	embed = discord.Embed(description=description, color=discord.Color.red())
	if title:
		embed.title = title
	return embed

def warning_embed(description: str, title: Optional[str] = None) -> discord.Embed:
	embed = discord.Embed(description=description, color=discord.Color.gold())
	if title:
		embed.title = title
	return embed

def info_embed(description: str, title: Optional[str] = None) -> discord.Embed:
	embed = discord.Embed(description=description, color=discord.Color.blurple())
	if title:
		embed.title = title
	return embed
