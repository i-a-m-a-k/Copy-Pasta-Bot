import discord

def handle_help(args: list[str]) -> discord.Embed:
	"""Generates categorized help embeds for CopyPastaBot commands."""

	if len(args) != 2:
		embed = discord.Embed(
			title="CopyPastaBot Help",
			description="Save custom copypastas, recall them dynamically, and use meme commands!",
			color=discord.Color.blurple()
		)
		embed.add_field(
			name="Basic Usage",
			value="• `;;<cmd>` : Run a bot command\n• `;;<key>;;` : Recall a saved text anywhere in your message",
			inline=False
		)
		embed.add_field(
			name="Detailed Categories",
			value="• `;;help copypasta` : Key storage, management, and searching\n• `;;help memes` : Meme generators, image deepfrying, text transformers",
			inline=False
		)
		embed.set_footer(text="Tip: You can attach images or reply to messages when saving keys!")
		return embed

	match args[1].lower():
		case 'copypasta':
			embed = discord.Embed(
				title="Copypasta Commands",
				description="Save, manage, and retrieve your custom copypastas.",
				color=discord.Color.blurple()
			)
			embed.add_field(
				name="Saving & Managing Keys",
				value=(
					"• **`add <key> <message>`** : Save text (or reply to message/attach media)\n"
					"• **`add_o <key> <message>`** : Save text and overwrite if exists\n"
					"• **`saved`** : Interactive paginated list of your saved keys\n"
					"• **`delete <key>`** : Delete a key\n"
					"• **`delkey`** : Delete key by replying to bot message\n"
					"• **`delete_me`** : Delete all your saved keys\n"
					"• **`rename <old> <new>`** : Rename a key\n"
					"• **`rename_o <old> <new>`** : Rename a key (overwrite)"
				),
				inline=False
			)
			embed.add_field(
				name="Finding & Stealing Keys",
				value=(
					"• **`steal <@user> <key> [new]`** : Steal a key from another user\n"
					"• **`vibematch <@user> [@user2]`** : Check meme compatibility percentage between users\n"
					"• **`random [term]`** : Send a random saved key (optional search filter)\n"
					"• **`search <term>`** : Search through your saved keys"
				),
				inline=False
			)
			embed.add_field(
				name="Backup & Transfer",
				value=(
					"• **`export`** : Export saved keys as JSON to your Direct Messages (DMs)\n"
					"• **`import`** : Import keys from JSON file (DM only, with overwrite warning)"
				),
				inline=False
			)
			return embed

		case 'memes':
			embed = discord.Embed(
				title="Meme Commands",
				description="Transform text and generate meme media by replying to messages.",
				color=discord.Color.blurple()
			)
			embed.add_field(
				name="Text Transformers (Reply to a message)",
				value=(
					"• **`mock`** : Mock a message with image\n"
					"• **`clap`** : Add 👏 between words\n"
					"• **`zalgo`** : Add cursed text effects\n"
					"• **`owo`** : OwOify text\n"
					"• **`copypasta`** : Generate copypasta emojis\n"
					"• **`stretch`** : Streeeeetch vowels\n"
					"• **`vaporwave`** : Ｃｏｎｖｅｒｔ ｔｏ ｆｕｌｌｗｉｄｔｈ\n"
					"• **`emojify`** : Convert text to 🇪 🇲 🇴 🇯 🇮 🇸\n"
					"• **`s <pattern> <replace> [flags]`** : Vim regex substitute"
				),
				inline=False
			)
			embed.add_field(
				name="Interactive & Media",
				value=(
					"• **`cat [-t tag] [-g] [text]`** : Cat image or GIF from Cataas (Reply / Text)\n"
					"• **`dadjoke [term]`** : Fetch a dad joke from icanhazdadjoke (Random / Search)\n"
					"• **`lmgtfy [query]`** : Generate a Google search link (Reply / Text)\n"
					"• **`thonkify <text>`** : Thinking emoji (🤔) font banner (Reply / Text)\n"
					"• **`deepfry`** : Deep fry image with eye flares (Reply / Attach)\n"
					"• **`roast <@user>`** : Roast a tagged user\n"
					"• **`flirt <@user>`** : Flirt with a tagged user\n"
					"• **`dream <prompt>`** : AI image & video generation (`-v`, `-i2v`, `-modify`, `-ar`, …)"
				),
				inline=False
			)
			return embed

		case 'admin':
			embed = discord.Embed(
				title="Admin Commands",
				description="Bot administration and moderation commands (Bot Admins only).",
				color=discord.Color.dark_red()
			)
			embed.add_field(
				name="Bot Moderation & Controls",
				value=(
					"• **`dream --ban <@user|id> [reason]`** : Ban user from `;;dream` (or reply)\n"
					"• **`dream --unban <@user|id>`** : Unban user from `;;dream` (or reply)\n"
					"• **`dream --banlist`** : View ephemeral dream banlist\n"
					"• **`blacklist_add <@user>`** : Blacklist user from the entire bot\n"
					"• **`blacklist_remove <@user>`** : Remove user from bot blacklist\n"
					"• **`revsearch`** : Reverse-search any replied message against saved keys (Bot Admin)\n"
					"• **`disable <cmd>`** : Disable command in current server (Mods+)\n"
					"• **`enable <cmd>`** : Enable disabled command in server (Mods+)\n"
					"• **`disable <cmd> -g`** : Globally disable command everywhere (Bot Admin)\n"
					"• **`enable <cmd> -g`** : Globally enable command everywhere (Bot Admin)\n"
					"• **`ping`** : View bot latency and system status"
				),
				inline=False
			)
			return embed

		case _:
			return handle_help([])
