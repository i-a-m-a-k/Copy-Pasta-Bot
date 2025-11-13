import discord
import utils.Constants as constants
import re
import shlex

class Message:
	def __init__(self, message_obj:discord.Message):
		self.message_obj = message_obj
		self.reference = getattr(message_obj, 'reference', None)
		self.reference = self.reference.resolved if self.reference else self.reference
		self.to_reference = getattr(message_obj, 'to_reference', None)
		self.author = message_obj.author

		self.content = self.get_content(message_obj) # populate self.content
		self.images = set(self.get_attachments(message_obj, attachment_type='image', check_reference=True))
		self.videos = set(self.get_attachments(message_obj, attachment_type='video', check_reference=True))
		self.audios = set(self.get_attachments(message_obj, attachment_type='audio', check_reference=True))

		self.mentions = getattr(message_obj, 'mentions', None)

		# Incase image is the only embed, content should be considered empty
		if len(self.images) == 1 and list(self.images)[0] == self.content:
			self.content = ''

		self.is_cmd = False
		self.replace = False
		self.args = None

		if self.content:
			if re.match(constants.COMMAND, self.content):
				self.is_cmd = True
				self.args = shlex.split(self.content[2:])
			elif re.match(constants.REPLACE, self.content):
				self.replace = True

	def get_content(self, message_obj:discord.Message):
		if message_obj.content != '': # Normal message
			return message_obj.content.strip()
		if len(message_obj.attachments) == 0:
			if message_obj.reference: # Forwarded message
				content = []
				if message_obj.reference:
					content += message_obj.reference.content.strip()
				if message_obj.reference.cached_message:
					content += message_obj.reference.cached_message.content.strip()
				return '\n'.join(content)

			if message_obj.embeds: # Embed message
				content = []
				for embed in message_obj.embeds:
					try:
						content.append(embed.content)
					except AttributeError:
						continue
				return '\n'.join(content)

	def get_attachments(self, message_obj:discord.Message, attachment_type:str, check_reference:bool=False):
		attachments = []
		if not message_obj:
			return attachments

		if message_obj.attachments:
			attachments += [attachment.url for attachment in message_obj.attachments if attachment.content_type[:5] == attachment_type]

		# Add code to read EmbedProxy for `thumbnail` when image is specified
		if message_obj.embeds and attachment_type != 'audio':
			attachments += [getattr(embed, attachment_type).url for embed in message_obj.embeds if getattr(embed, attachment_type).__repr__() != 'EmbedProxy()']

		if message_obj.embeds and attachment_type == 'image':
			attachments += [getattr(embed, 'thumbnail').url for embed in message_obj.embeds if getattr(embed, 'thumbnail').__repr__() != 'EmbedProxy()']

		# Checks for forwarded messages
		if check_reference and message_obj.reference:
			try:
				attachments += self.get_attachments(message_obj.reference, attachment_type, check_reference=False)
				attachments += self.get_attachments(message_obj.reference.cached_message, attachment_type, check_reference=False)
			except:
				pass

		return attachments
