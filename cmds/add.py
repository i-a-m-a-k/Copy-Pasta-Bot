import constants
from DatabaseManager import DatabaseManager
from Message import Message

def add(message: Message, db: DatabaseManager, overwrite:bool=False) -> str:
	args = message.args
	reply = Message(message.reference.resolved) if message.reference else None
	if len(args) == 1:
		return constants.WRONG_ARGS_ADD

	if len(args) == 2:
		if reply is None and len(message.message_obj.attachments) == 0:
			return constants.WRONG_ARGS_ADD

		if reply:
			# original_message = reply.resolved.content.strip() or ''
			original_message = reply.content.strip() or ''
			original_message += _get_attachments_text(reply)
		else:
			original_message = ''
		original_message += _get_attachments_text(message)

		if not original_message:
			return constants.EMPTY_MESSAGE

		return db.store_text(message.author.id, args[1], original_message, overwrite)

	return db.store_text(message.author.id, args[1], ' '.join(args[2:]), overwrite)

def _get_attachments_text(message: Message) -> str:
	text = ''
	# for i, attachment in enumerate(message.attachments):
	# 	text += f'[Attachment {i}]({attachment.url}) '
	# for sticker in message.stickers:
	# 	text += f'[{sticker.name}]({sticker.url}) '

	for i, url in enumerate(message.images):
		text += f'[Image {i}]({url}) '
	for i, url in enumerate(message.videos):
		text += f'[Video {i}]({url}) '
	for i, url in enumerate(message.audios):
		text += f'[Audio {i}]({url}) '
	return text
