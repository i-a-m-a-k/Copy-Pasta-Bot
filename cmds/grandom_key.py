from sqlitedict import SqliteDict
import constants
import random

def grandom_key(db: SqliteDict, search_term: str=None) -> str:
	if search_term is None:
		users_with_keys = [user for user in db.keys() if db.get(user, {})]
		if not users_with_keys:
			return constants.EMPTY_LIST
			
		random_user = random.choice(users_with_keys)
		user_db = db.get(random_user, {})
		return random.choice(list(user_db.values()))

	all_values = []
	for user in db.keys():
		user_db = db.get(user, {})
		for key, value in user_db.items():
			if search_term in key:
				all_values.append(value)
				
	if not all_values:
		return constants.EMPTY_LIST
		
	return random.choice(all_values)
