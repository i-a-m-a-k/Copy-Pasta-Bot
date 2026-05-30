from sqlitedict import SqliteDict
import constants

def search(db:SqliteDict, user:str, search_key:str) -> str:
	user_db = db.get(user, None)
	if user_db is None:
		return constants.EMPTY_LIST

	results = sorted([f'- {x}' for x in user_db.keys() if search_key in x])
	return '\n'.join(results) if results else f"No keys found matching `{search_key}`."