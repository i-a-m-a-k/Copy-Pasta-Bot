import asyncio
import os
import re
import sys
from datetime import datetime, timedelta, timezone
import discord
from sqlitedict import SqliteDict
import constants
import do_not_push
from cmds import *  # noqa: F403
from DatabaseManager import DatabaseManager
from CommandHandler import CommandHandler
from Message import Message

sys.path.append(os.path.basename(__file__))

class DiscordBot:
	def __init__(self, token: str):
		self.token = token
		intents = discord.Intents.default()
		intents.message_content = True
		self.client = discord.Client(intents=intents)
		self.db_manager = DatabaseManager(constants.DB_NAME)
		self.command_handler = CommandHandler(self.db_manager, self._get_user)
		self.setup_events()

	def _get_user(self):
		return self.client.user

	async def update_status(self):
		while True:
			try:
				total_users = sum(guild.member_count for guild in self.client.guilds)
				total_servers = len(self.client.guilds)
				status = f'Serving {total_users}+ users in {total_servers} servers'
				await self.client.change_presence(activity=discord.Activity(
					type=discord.ActivityType.custom,
					name=status,
					state=status
				))
			except Exception as e:
				print(f"Error updating status: {e}", file=sys.stderr)
			await asyncio.sleep(86400)

	def setup_events(self):
		@self.client.event
		async def on_ready():
			print(f'Logged in as {self.client.user}')
			asyncio.create_task(self.update_status())

		@self.client.event
		async def on_message(message: discord.Message):
			if message.author == self.client.user or message.author.bot:
				return

			if not blacklist.is_blacklisted(message.author.id):
				return constants.BLACKLISTED

			mess = Message(message)
			await self.process_message(mess)

		@self.client.event
		async def on_reaction_add(reaction, user:discord.User):
			if user == self.client.user:
				return

			message = reaction.message

			if not message.channel.permissions_for(message.channel.guild.me).manage_messages or \
				not message.channel.permissions_for(message.channel.guild.me).add_reactions:
				return

			if message.author != self.client.user:
				return

			if message.created_at < datetime.now(timezone.utc) - timedelta(minutes=5):
				return

			if not message.content.strip().startswith(constants.SAVED_MSGS):
				return

			# Message format:
			# Saved messages for: <@userid>
			# Pageno/total
			# <content>

			message_lines = message.content.strip().split('\n')
			numbers = re.findall(r'\d+', message_lines[0]) # Should only contain 1 element
			if len(numbers) != 1:
				print('Error updating saved message: Can\'t find author id in: ', message_lines[0], file=sys.stderr)
				return

			author = numbers[0]
			if author != str(user.id):
				await reaction.remove(user)
				return
			try:
				page_no = int(message_lines[1].split('/')[0]) - 1
			except ValueError:
				print('Error updating saved message: Can\'t find page no in: ', message_lines[1], file=sys.stderr)
				return
			except Exception as e:
				print('Error updating saved message: Unknown error lmao ' + str(e) , file=sys.stderr)
				return

			user_saved = sorted(self.db_manager.get_user_keys(author))
			pages = [user_saved[i:i+10] for i in range(0, len(user_saved), 10)]

			match reaction.emoji:
				case '▶️':
					new_page = page_no + 1
					if len(pages) <= new_page:
						await reaction.remove(user)
						return
					else:
						new_content = f'{constants.SAVED_MSGS} <@{author}>\n' +\
										f'{str(new_page+1)}/{str(len(pages))}\n' +\
										'- ' + '\n- '.join(pages[new_page])
						await message.edit(content=new_content)

				case '⏭️':
					new_content = f'{constants.SAVED_MSGS} <@{author}>\n' +\
									f'{str(len(pages))}/{str(len(pages))}\n' +\
									'- ' + '\n- '.join(pages[-1])
					await message.edit(content=new_content)

				case '◀️':
					new_page = page_no - 1
					if 0 > new_page:
						await reaction.remove(user)
						return
					else:
						new_content = f'{constants.SAVED_MSGS} <@{author}>\n' +\
										f'{str(new_page+1)}/{str(len(pages))}\n' +\
										'- ' + '\n- '.join(pages[new_page])
						await message.edit(content=new_content)

				case '⏮️':
					new_content = f'{constants.SAVED_MSGS} <@{author}>\n' +\
									f'0/{str(len(pages))}\n' +\
									'- ' + '\n- '.join(pages[0])
					await message.edit(content=new_content)

				case _:
					await reaction.remove(user)
					return

			try:
				# await message.clear_reactions()
				# await message.add_reaction('⏮️')
				# await message.add_reaction('◀️')
				# await message.add_reaction('▶️')
				# await message.add_reaction('⏭️')
				await reaction.remove(user)
			except discord.HTTPException:
				print('Error removing reactions', file=sys.stderr)
			except Exception as e:
				print(e, file=sys.stderr)


	async def process_message(self, message: Message):
		content = message.content
		if re.search(constants.REPLACE, content):
			await self.handle_replacement(message)
		elif re.match(constants.COMMAND, content):
			await self.handle_bot_command(message)

	async def handle_replacement(self, message: Message):
		def get_text(match:re.Match)->str:
			key = match.string[match.start()+2:match.end()-2]
			replacement = self.db_manager.retrieve_text(message.author.id, key)
			if replacement:
				return replacement
			return f';;{key};;'

		replaced_text = re.sub(constants.REPLACE,
				get_text,
				message.content).strip()
		if replaced_text != message.content and replaced_text != '':
			target = message.reference.resolved if message.reference else message.message_obj
			await target.reply(replaced_text)

	async def handle_bot_command(self, message: Message):
		response = await self.command_handler.handle_command(message)

		if response:
			await self.send_response(message, response)

	async def send_response(self, message: Message, response):
		message_obj = message.message_obj
		cmd = message_obj.content.strip()[2:]
		reply_to = message.reference.resolved if message.reference and cmd.split()[0] in {
			'mock', 'deepfry', 'clap', 'zalgo', 'forbesify', 'copypasta', 'owo', 'stretch', 'random'
		} else message.message_obj

		if isinstance(response, discord.File):
			await reply_to.reply(file=response)
			if hasattr(response.fp, 'name'):
				os.remove(response.fp.name)
		elif isinstance(response, str):
			if len(response) > 2000:
				# Always reply to the command message for error responses
				await message.reply("## Fuck me! Keep it under the 2k character limit of Discord.")
			else:
				resp = await reply_to.reply(response)
				if cmd == 'saved':
					if response.strip().startswith(constants.SAVED_MSGS):
						message_obj = message.message_obj
						if isinstance(message_obj.channel, discord.TextChannel) or isinstance(message_obj.channel, discord.VoiceChannel):
							if message_obj.channel.permissions_for(message_obj.channel.guild.me).add_reactions and \
								message_obj.channel.permissions_for(message_obj.channel.guild.me).manage_messages:
								await resp.add_reaction('⏮️')
								await resp.add_reaction('◀️')
								await resp.add_reaction('▶️')
								await resp.add_reaction('⏭️')
		else:
			print("Unhandled response type:", type(response))

	def run(self):
		try:
			self.client.run(self.token)
		except Exception as e:
			print(f"Error: {e}")
		finally:
			# To avoid another data loss due to DB file getting deleted while bot is running
			if not os.path.exists(constants.DB_NAME):
				os.makedirs(os.path.dirname(constants.DB_NAME))
				os.mknod(constants.DB_NAME)
				backup_db = self.db_manager.copy_database(SqliteDict(constants.DB_NAME + '.bkp', autocommit=True))
				backup_db.close()
			self.db_manager.close()

if __name__ == '__main__':
	bot = DiscordBot(do_not_push.API_TOKEN)
	bot.run()
