import discord
from sqlitedict import SqliteDict

# Function to delete all of the user's saved data
def delete_me(db:SqliteDict, user:str)->bool:
	"""Delete all of the user's saved data. Returns True if data existed."""
	return db.pop(user, None) is not None