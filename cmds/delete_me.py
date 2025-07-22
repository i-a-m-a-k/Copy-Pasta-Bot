import constants
from DatabaseManager import DatabaseManager

# Function to delete all of the user's saved data
def delete_me(db: DatabaseManager, user:str) -> str:
	return constants.SUCCESSFUL if db.delete_user(user) else constants.EMPTY_LIST
