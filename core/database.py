from typing import Optional, Union
import discord
from sqlitedict import SqliteDict
import constants

class DatabaseManager:
	"""
	Database manager encapsulating SqliteDict key-value operations
	with an in-memory write-through cache and transparent dual integer/string
	Discord user ID resolution.
	"""
	def __init__(self, db_name: str, preload: bool = True):
		self.db = SqliteDict(db_name, autocommit=True)
		self._cache: dict[Union[int, str], dict[str, str]] = {}

		if preload:
			self._preload_cache()

	def _preload_cache(self):
		"""Warms the in-memory cache with all existing entries from SQLite on startup."""
		try:
			for user_key in self.db.keys():
				self._cache[user_key] = dict(self.db[user_key])
		except Exception as e:
			print(f"Notice: Cache preload encountered: {e}")

	def _get_user_entry(self, user: Union[int, str, discord.User, discord.Member]) -> tuple[Union[int, str], dict]:
		"""
		Resolves a user identifier to a tuple of (normalized_user_key, user_dictionary).
		Hits the in-memory cache first; falls back to SQLite unpickling if not cached.
		"""
		if hasattr(user, 'id'):
			user = user.id

		# 1. Fast RAM Cache Lookup
		if user in self._cache:
			return user, self._cache[user]

		alt_user = str(user) if isinstance(user, int) else (int(user) if str(user).isdigit() else user)
		if alt_user in self._cache:
			return alt_user, self._cache[alt_user]

		# 2. SQLite Fallback (Cold Cache Miss)
		if user in self.db:
			entry = dict(self.db[user])
			self._cache[user] = entry
			return user, entry

		if alt_user in self.db:
			entry = dict(self.db[alt_user])
			self._cache[alt_user] = entry
			return alt_user, entry

		# 3. New User Entry
		new_entry: dict[str, str] = {}
		self._cache[user] = new_entry
		return user, new_entry

	def store_text(self, user: Union[int, str, discord.User, discord.Member], key: str, value: str, overwrite: bool = False) -> str:
		"""Stores or updates a text key with write-through memory caching."""
		if len(key) > constants.MAX_KEY_LENGTH:
			return constants.KEY_TOO_LONG
		if len(value) > constants.MAX_VALUE_LENGTH:
			return constants.VALUE_TOO_LONG

		key_user, user_db = self._get_user_entry(user)
		if key in user_db and not overwrite:
			return constants.KEY_EXISTS_ADD

		if key not in user_db and len(user_db) >= constants.MAX_KEYS_PER_USER:
			return constants.KEY_LIMIT_REACHED

		user_db[key] = value
		# Write-through to SQLite and cache
		self.db[key_user] = user_db
		self._cache[key_user] = user_db
		return constants.SUCCESSFUL

	def retrieve_text(self, user: Union[int, str, discord.User, discord.Member], key: str) -> Optional[str]:
		"""Instant O(1) in-memory key lookup."""
		_, user_db = self._get_user_entry(user)
		return user_db.get(key)

	def get_user_keys(self, user: Union[int, str, discord.User, discord.Member]) -> list[str]:
		"""Instant in-memory list of saved keys."""
		_, user_db = self._get_user_entry(user)
		return list(user_db.keys())

	def rename_key(self, user: Union[int, str, discord.User, discord.Member], old_key: str, new_key: str, overwrite: bool = False) -> int:
		"""
		Renames an existing key with write-through cache update.
		Returns:
		 0 on success
		-1 if user has no keys
		-2 if old_key does not exist
		-3 if new_key exists and overwrite is False
		-4 if new_key exceeds MAX_KEY_LENGTH
		"""
		if len(new_key) > constants.MAX_KEY_LENGTH:
			return -4

		key_user, user_db = self._get_user_entry(user)
		if not user_db:
			return -1
		if old_key not in user_db:
			return -2
		if new_key in user_db and not overwrite:
			return -3

		user_db[new_key] = user_db.pop(old_key)
		self.db[key_user] = user_db
		self._cache[key_user] = user_db
		return 0

	def delete_key(self, user: Union[int, str, discord.User, discord.Member], key: str) -> bool:
		"""Deletes a key with write-through update to SQLite and memory cache."""
		key_user, user_db = self._get_user_entry(user)
		if key in user_db:
			del user_db[key]
			self.db[key_user] = user_db
			self._cache[key_user] = user_db
			return True
		return False

	def clear_user_keys(self, user: Union[int, str, discord.User, discord.Member]) -> bool:
		"""Mass-deletes all keys for a user in memory cache and SQLite."""
		key_user, user_db = self._get_user_entry(user)
		if user_db:
			user_db.clear()
			self.db[key_user] = user_db
			self._cache[key_user] = user_db
			return True
		return False

	def get_all_users(self) -> dict[Union[int, str], dict[str, str]]:
		"""Returns all in-memory user dictionaries for fast global operations."""
		return self._cache

	def find_all_keys_by_value(self, value: str, user: Optional[Union[int, str, discord.User, discord.Member]] = None) -> list[tuple[Union[int, str], str]]:
		"""
		Reverse-lookup: finds all (user_id, key) pairs matching the given content.
		If user is provided, searches only that user's entries.
		Scans the preloaded in-memory cache with zero SQLite read overhead.
		"""
		results = []
		normalized_value = value.strip()

		if user is not None:
			user_id_key, user_db = self._get_user_entry(user)
			for key, stored_value in user_db.items():
				if stored_value.strip() == normalized_value:
					results.append((user_id_key, key))
			return results

		# Iterate fast in-memory cache
		for user_id, user_db in self._cache.items():
			for key, stored_value in user_db.items():
				if stored_value.strip() == normalized_value:
					results.append((user_id, key))
		return results

	def copy_database(self, new_db: SqliteDict) -> SqliteDict:
		"""Copies all entries to a target backup database."""
		for key in self.db.keys():
			new_db[key] = self.db[key]
		return new_db

	def import_user_keys(
		self,
		user: Union[int, str, discord.User, discord.Member],
		keys_dict: dict[str, str],
		overwrite: bool = True
	) -> tuple[int, int]:
		"""
		Atomically imports multiple keys into a user's database with a single SQLite write.
		Returns (new_keys_count, overwritten_keys_count).
		"""
		key_user, user_db = self._get_user_entry(user)
		new_count = 0
		overwritten_count = 0

		for k, v in keys_dict.items():
			if k in user_db:
				if overwrite:
					user_db[k] = v
					overwritten_count += 1
			else:
				if len(user_db) < constants.MAX_KEYS_PER_USER:
					user_db[k] = v
					new_count += 1

		self.db[key_user] = user_db
		self._cache[key_user] = user_db
		return new_count, overwritten_count

	def close(self):
		"""Flushes and closes the underlying SQLite connection."""
		self.db.close()

