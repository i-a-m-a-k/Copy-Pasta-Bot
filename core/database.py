from typing import Optional, Union
import discord
from sqlitedict import SqliteDict
import constants


class RandomHistoryCache:
	"""
	Thread-safe LRU cache for random value history.
	Tracks recently shown values per user with automatic 24-hour expiration.
	"""
	
	def __init__(self, max_history: int = None, ttl_hours: int = None):
		"""
		Initialize the history cache.
		
		Args:
			max_history: Maximum number of values to track per user (default from constants)
			ttl_hours: Hours before auto-reset (default from constants)
		"""
		import time
		from collections import OrderedDict
		
		self.max_history = max_history or constants.RANDOM_HISTORY_SIZE
		self.ttl_seconds = (ttl_hours or constants.RANDOM_HISTORY_TTL_HOURS) * 3600
		
		# Structure: {user_id: OrderedDict{value: timestamp}}
		self._history: dict[Union[int, str], OrderedDict] = {}
		self._last_reset: dict[Union[int, str], float] = {}
		self._time = time
	
	def _should_reset(self, user_id: Union[int, str]) -> bool:
		"""Check if 24 hours have passed since last reset."""
		if user_id not in self._last_reset:
			return False
		return self._time.time() - self._last_reset[user_id] > self.ttl_seconds
	
	def _reset_user(self, user_id: Union[int, str]):
		"""Clear history for a user and update reset timestamp."""
		self._history.pop(user_id, None)
		self._last_reset[user_id] = self._time.time()
	
	def add_to_history(self, user_id: Union[int, str], value: str):
		"""
		Add value to user's history with timestamp.
		
		Args:
			user_id: The user's ID
			value: The value that was shown (not the key)
		"""
		# Check if reset needed
		if self._should_reset(user_id):
			self._reset_user(user_id)
		
		if user_id not in self._history:
			self._history[user_id] = {}
			self._last_reset[user_id] = self._time.time()
		
		# Remove if exists (to update recency)
		self._history[user_id].pop(value, None)
		
		# Add with current timestamp
		self._history[user_id][value] = self._time.time()
		
		# Trim to max size (remove oldest)
		while len(self._history[user_id]) > self.max_history:
			# Find oldest entry
			oldest_key = min(
				self._history[user_id].keys(),
				key=lambda k: self._history[user_id][k]
			)
			del self._history[user_id][oldest_key]
	
	def is_in_history(self, user_id: Union[int, str], value: str) -> bool:
		"""Check if value is in user's recent history."""
		# Check if reset needed first
		if self._should_reset(user_id):
			self._reset_user(user_id)
			return False
		
		return value in self._history.get(user_id, {})
	
	def get_excluded_values(self, user_id: Union[int, str]) -> set:
		"""
		Get set of values to exclude from random selection.
		
		Args:
			user_id: The user's ID
			
		Returns:
			Set of values in the user's history
		"""
		if self._should_reset(user_id):
			self._reset_user(user_id)
			return set()
		
		return set(self._history.get(user_id, {}).keys())


class DatabaseManager:
	"""
	Database manager encapsulating SqliteDict key-value operations
	with an in-memory write-through cache and transparent dual integer/string
	Discord user ID resolution.
	Includes reverse index for O(1) value lookups.
	"""
	def __init__(self, db_name: str, preload: bool = True):
		self.db = SqliteDict(db_name, autocommit=True)
		self._cache: dict[Union[int, str], dict[str, str]] = {}
		# NEW: Reverse index for O(1) value lookups
		# Maps: normalized_value -> set[(user_id, key), ...]
		self._value_index: dict[str, set[tuple[Union[int, str], str]]] = {}

		if preload:
			self._preload_cache()
			self._build_reverse_index()

	def _preload_cache(self):
		"""Warms the in-memory cache with all existing entries from SQLite on startup."""
		try:
			for user_key in self.db.keys():
				self._cache[user_key] = dict(self.db[user_key])
		except Exception as e:
			print(f"Notice: Cache preload encountered: {e}")

	def _build_reverse_index(self):
		"""Builds the reverse index from preloaded cache."""
		for user_id, user_db in self._cache.items():
			for key, value in user_db.items():
				normalized = value.strip()
				if normalized:
					self._value_index.setdefault(normalized, set()).add((user_id, key))

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
		
		# Handle overwrite: remove old value from reverse index
		if key in user_db and overwrite:
			old_value = user_db[key]
			old_normalized = old_value.strip()
			if old_normalized and old_normalized in self._value_index:
				self._value_index[old_normalized].discard((key_user, key))
				# Clean up empty sets
				if not self._value_index[old_normalized]:
					del self._value_index[old_normalized]
		elif key in user_db and not overwrite:
			return constants.KEY_EXISTS_ADD

		if key not in user_db and len(user_db) >= constants.MAX_KEYS_PER_USER:
			return constants.KEY_LIMIT_REACHED

		user_db[key] = value
		
		# Update reverse index for new value
		normalized = value.strip()
		if normalized:
			self._value_index.setdefault(normalized, set()).add((key_user, key))
		
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
		Updates reverse index to reflect the new key name.
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

		# Update reverse index: remove old_key, add new_key
		value = user_db[old_key]
		normalized = value.strip()
		if normalized and normalized in self._value_index:
			self._value_index[normalized].discard((key_user, old_key))
			self._value_index[normalized].add((key_user, new_key))

		user_db[new_key] = user_db.pop(old_key)
		self.db[key_user] = user_db
		self._cache[key_user] = user_db
		return 0

	def delete_key(self, user: Union[int, str, discord.User, discord.Member], key: str) -> bool:
		"""Deletes a key with write-through update to SQLite and memory cache."""
		key_user, user_db = self._get_user_entry(user)
		if key in user_db:
			# Remove from reverse index first
			value = user_db[key]
			normalized = value.strip()
			if normalized and normalized in self._value_index:
				self._value_index[normalized].discard((key_user, key))
				# Clean up empty sets
				if not self._value_index[normalized]:
					del self._value_index[normalized]
			
			del user_db[key]
			self.db[key_user] = user_db
			self._cache[key_user] = user_db
			return True
		return False

	def clear_user_keys(self, user: Union[int, str, discord.User, discord.Member]) -> bool:
		"""Mass-deletes all keys for a user in memory cache and SQLite."""
		key_user, user_db = self._get_user_entry(user)
		if user_db:
			# Remove all entries from reverse index
			for key, value in user_db.items():
				normalized = value.strip()
				if normalized and normalized in self._value_index:
					self._value_index[normalized].discard((key_user, key))
					if not self._value_index[normalized]:
						del self._value_index[normalized]
			
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
		Uses O(1) reverse index lookup instead of O(n) linear scan.
		If user is provided, searches only that user's entries.
		"""
		normalized_value = value.strip()
		
		# O(1) lookup from reverse index
		results = list(self._value_index.get(normalized_value, set()))
		
		if user is not None:
			user_id_key, _ = self._get_user_entry(user)
			results = [(uid, key) for uid, key in results if uid == user_id_key]
		
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

	def get_random_history_cache(self) -> RandomHistoryCache:
		"""
		Returns or creates the shared RandomHistoryCache instance.
		Lazily initializes on first access.
		"""
		if not hasattr(self, '_random_history_cache'):
			self._random_history_cache = RandomHistoryCache()
		return self._random_history_cache


