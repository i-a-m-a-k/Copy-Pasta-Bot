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
					"• **`random [term]`** : Send a random saved key (optional search filter)\n"
					"• **`search <term>`** : Search through your saved keys"
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
					"• **`deepfry`** : Deep fry image with eye flares (Reply / Attach)\n"
					"• **`roast <@user>`** : Roast a tagged user\n"
					"• **`flirt <@user>`** : Flirt with a tagged user\n"
					"• **`dream <prompt>`** : AI image & video generation (`-v`, `-i2v`)"
				),
				inline=False
			)
			return embed

		case _:
			return handle_help([])
