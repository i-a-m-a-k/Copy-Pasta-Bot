import utils.Constants as constants
from utils.DatabaseManager import DatabaseManager
from utils.Message import Message


def add(message: Message, db: DatabaseManager, overwrite: bool = False) -> str:
	args = message.args
	reply = Message(message.reference) if message.reference else None

	if len(args) == 1:
		return constants.WRONG_ARGS_ADD

	if len(args) == 2:
		if reply is None and len(message.message_obj.attachments) == 0:
			return constants.WRONG_ARGS_ADD

		original_message = ""
		if reply:
			original_message = (getattr(reply, "content", "") or "").strip()
			original_message += _get_attachments_text(reply)
		else:
			original_message = _get_attachments_text(message)

		if not original_message:
			return constants.EMPTY_MESSAGE

		return db.store_text(message.author.id, args[1], original_message, overwrite)

	return db.store_text(message.author.id, args[1], " ".join(args[2:]), overwrite)


def _get_attachments_text(message: Message) -> str:
    text = ""

    for i, url in enumerate(message.images):
        text += f"[Image {i}]({url}) "
    for i, url in enumerate(message.videos):
        text += f"[Video {i}]({url}) "
    for i, url in enumerate(message.audios):
        text += f"[Audio {i}]({url}) "

    return text
