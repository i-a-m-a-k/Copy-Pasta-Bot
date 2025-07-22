from DatabaseManager import DatabaseManager
import constants
import discord

# def _search(db:SqliteDict, user:str, search_key:str) -> str:
# 	user_db = db.get(user, None)
# 	if user_db is None:
# 		return constants.EMPTY_LIST

# 	return '\n'.join(sorted([f'- {x}' for x in user_db.keys() if search_key in x]))

def handle_search(db: DatabaseManager, user: discord.User, args: list):
    search_term = args[1]
    keys = db.get_user_keys(user.id)

    if not keys:
        return constants.EMPTY_LIST

    return "- " + "\n- ".join(sorted(k for k in keys if search_term in k))
