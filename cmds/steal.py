from sqlitedict import SqliteDict
import constants

def steal(db:SqliteDict, user:str, key:str, steal_from:str, new_key:str=None) -> str:
	steal_from_db = db.get(steal_from, None)
	if steal_from_db is None:
		return constants.EMPTY_LIST_STEAL
	
	value = steal_from_db.get(key, None)
	if value is None:
		return constants.KEY_NOT_FOUND
	
	user_db = db.get(user, None)
	if user_db is None:
		user_db = {}
	if new_key is None:
		if user_db.get(key, None) is not None:
			return constants.KEY_EXISTS_STEAL
	else:
		key = new_key
	
	user_db[key] = value
	db[user] = user_db

	return constants.SUCCESSFUL
	