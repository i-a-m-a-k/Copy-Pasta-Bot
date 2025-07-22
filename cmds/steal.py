import discord
import constants
from DatabaseManager import DatabaseManager

def _steal(db:DatabaseManager, user:str, key:str, steal_from:str, new_key=None) -> str:
	# steal_from_db = db.get(steal_from, None)
	steal_from_keys = db.get_user_keys(steal_from)
	if steal_from_keys is None:
		return constants.EMPTY_LIST_STEAL

	# value = steal_from_db.get(key, None)
	# if value is None:
	# 	return constants.KEY_NOT_FOUND

	if key not in steal_from_keys:
		return constants.KEY_NOT_FOUND

	# WHY???
	# user_db = db.get(user, None)
	# if user_db is None:
	# 	return constants.EMPTY_LIST

	# if new_key is None:
	# 	# if user_db.get(key, None) is not None:
	# 	# 	return constants.KEY_EXISTS_STEAL
	# 	if key in
	# else:
	# 	key = new_key

	# user_db[key] = value
	# db[user] = user_db

	user_keys = db.get_user_keys(user)

	if new_key is None:
		new_key = key

	if new_key in user_keys:
		return constants.KEY_EXISTS_STEAL

	db.store_text(user, new_key, db.retrieve_text(steal_from, key))
	return constants.SUCCESSFUL

def handle_steal(db:DatabaseManager, user: discord.User, args: list) -> str:
	if len(args) == 2 and '<@' in args[1]:
		return constants.WRONG_ARGS_STEAL
	elif len(args) not in {3, 4}:
		return constants.WRONG_ARGS

	steal_from = args[1]
	if not steal_from.startswith('<@') or not steal_from.endswith('>'):
		return constants.WRONG_USER_ID

	steal_from = steal_from[2:-1]
	new_key = args[3] if len(args) == 4 else None
	return _steal(db, user.id, args[2], steal_from, new_key)
