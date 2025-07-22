import random
from typing import Optional
import discord
import constants
from DatabaseManager import DatabaseManager

def _random_key(db: DatabaseManager, user: str, search_term:Optional[str]=None) -> str:
	# user_db = db.get(user, None)

	# if user_db is None:
	# 	return constants.EMPTY_LIST

	user_keys = db.get_user_keys(user)

	if search_term is not None:
		user_keys = [key for key in user_keys if search_term in key]

	if not user_keys:
		return constants.EMPTY_LIST

	# return user_db[random.choice(list(user_db.keys()))]
	return db.retrieve_text(user, random.choice(user_keys))

def handle_random(user: discord.User, args:list, db:DatabaseManager) -> str:
	if len(args) != 1 and len(args) != 2:
		return constants.WRONG_ARGS

	search_term = args[1] if len(args) == 2 else None
	return _random_key(db, str(user.id), search_term)
