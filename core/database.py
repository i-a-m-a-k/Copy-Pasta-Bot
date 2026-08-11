from typing import Optional, Union
import discord
from sqlitedict import SqliteDict
import constants

class DatabaseManager:
	"""
	Database manager encapsulating SqliteDict key-value operations
	with transparent dual integer/string Discord user ID resolution.
	"""
	def __init__(self, db_name: str):
		self.db = SqliteDict(db_name, autocommit=True)

	def _get_user_entry(self, user: Union[int, str, discord.User, discord.Member]) -> tuple[Union[int, str], dict]:
		"""
		Resolves a user identifier to a tuple of (normalized_user_key, user_dictionary).
		Handles dual integer and string keys gracefully.
		"""
		if hasattr(user, 'id'):
			user = user.id

		if user in self.db:
			return user, self.db[user]

		alt_user = str(user) if isinstance(user, int) else (int(user) if str(user).isdigit() else user)
		if alt_user in self.db:
			return alt_user, self.db[alt_user]

		return user, {}

	def store_text(self, user: Union[int, str, discord.User, discord.Member], key: str, value: str, overwrite: bool = False) -> str:
		key_user, user_db = self._get_user_entry(user)
		if key in user_db and not overwrite:
			return constants.KEY_EXISTS_ADD
		user_db[key] = value
		self.db[key_user] = user_db
		return constants.SUCCESSFUL

	def retrieve_text(self, user: Union[int, str, discord.User, discord.Member], key: str) -> Optional[str]:
		_, user_db = self._get_user_entry(user)
		return user_db.get(key)

	def get_user_keys(self, user: Union[int, str, discord.User, discord.Member]) -> list[str]:
		_, user_db = self._get_user_entry(user)
		return list(user_db.keys())

	def delete_key(self, user: Union[int, str, discord.User, discord.Member], key: str) -> bool:
		key_user, user_db = self._get_user_entry(user)
		if key in user_db:
			del user_db[key]
			self.db[key_user] = user_db
			return True
		return False

	def find_all_keys_by_value(self, value: str) -> list[tuple[Union[int, str], str]]:
		"""
		Reverse-lookup: find all (user_id, key) pairs that store this value.
		Comparison is whitespace-normalized to handle trailing spaces from attachment/sticker formatting.
		"""
		results = []
		normalized_value = value.strip()
		for user_id in self.db.keys():
			user_db = self.db.get(user_id, {})
			for key, stored_value in user_db.items():
				if stored_value.strip() == normalized_value:
					results.append((user_id, key))
		return results

	def copy_database(self, new_db: SqliteDict) -> SqliteDict:
		"""Copies all entries to a target backup database."""
		for key in self.db.keys():
			new_db[key] = self.db[key]
		return new_db

	def close(self):
		"""Closes the underlying SQLite connection."""
		self.db.close()
