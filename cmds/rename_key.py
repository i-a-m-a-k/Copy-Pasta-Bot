import constants
from DatabaseManager import DatabaseManager
from Message import Message

def _rename_key(db:DatabaseManager, user:str, key:str, new_key:str, overwrite:bool) -> str:
	user_keys = db.get_user_keys(user)
	if not user_keys:
		return constants.EMPTY_LIST

	value = db.retrieve_text(user, key)
	if not value:
		return constants.KEY_NOT_FOUND

	if db.retrieve_text(user, new_key) and not overwrite:
		return constants.KEY_EXISTS_RENAME

	db.store_text(user, new_key, value, overwrite)
	db.delete_key(user, key)

	return constants.SUCCESSFUL

def handle_rename(message: 'Message', db:DatabaseManager, overwrite: bool=False) -> str:
	if len(message.args) != 3:
		return constants.WRONG_ARGS_RENAME
	return _rename_key(db, message.author.id, message.args[1], message.args[2], overwrite)
