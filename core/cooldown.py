import time
import math
from typing import Optional, Union

class CooldownEntry:
	__slots__ = ('expires_at', 'duration', 'warned')

	def __init__(self, expires_at: float, duration: float):
		self.expires_at = expires_at
		self.duration = duration
		self.warned = False  # Track if warning embed was already delivered for this window


class CooldownManager:
	"""
	Centralized cooldown manager with per-(user, command) tracking,
	live Discord relative timestamp formatting (<t:ts:R>), spam suppression,
	and automatic memory pruning.
	"""
	def __init__(self, default_cooldown: float = 10.0, dream_cooldown: float = 60.0):
		self.default_cooldown = default_cooldown
		self.dream_cooldown = dream_cooldown
		self._cooldowns: dict[tuple[int, str], CooldownEntry] = {}

	def get_cooldown_duration(self, command: str) -> float:
		"""Returns the configured cooldown duration for a command in seconds."""
		if command == 'dream':
			return self.dream_cooldown
		return self.default_cooldown

	def check(self, user_id: int, command: str) -> Optional[tuple[float, int, bool]]:
		"""
		Checks if a user is currently on cooldown for a specific command.

		Returns:
			None: If not on cooldown (can proceed).
			tuple: (time_remaining, expires_timestamp, should_warn)
				- time_remaining: Float seconds until cooldown expiry.
				- expires_timestamp: Integer Unix timestamp for Discord formatting.
				- should_warn: True on the first attempt during this cooldown window;
				               False on subsequent spam attempts during the same window.
		"""
		now = time.time()
		key = (user_id, command)

		entry = self._cooldowns.get(key)
		if entry is None:
			return None

		if now >= entry.expires_at:
			# Expired; self-prune
			del self._cooldowns[key]
			return None

		# Still on cooldown
		time_remaining = entry.expires_at - now
		expires_timestamp = int(math.ceil(entry.expires_at))

		if not entry.warned:
			entry.warned = True
			should_warn = True
		else:
			should_warn = False

		return (time_remaining, expires_timestamp, should_warn)

	def trigger(self, user_id: int, command: str, custom_duration: Optional[float] = None) -> float:
		"""
		Starts or refreshes a cooldown window for (user_id, command).
		Also periodically purges stale records to avoid unbounded RAM growth.
		"""
		now = time.time()
		duration = custom_duration if custom_duration is not None else self.get_cooldown_duration(command)
		expires_at = now + duration
		self._cooldowns[(user_id, command)] = CooldownEntry(expires_at, duration)

		if len(self._cooldowns) > 500:
			self.prune_expired()

		return duration

	def reset(self, user_id: int, command: str):
		"""Clears the cooldown for a user and command."""
		self._cooldowns.pop((user_id, command), None)

	def prune_expired(self):
		"""Removes all expired entries from memory."""
		now = time.time()
		expired_keys = [k for k, v in self._cooldowns.items() if now >= v.expires_at]
		for k in expired_keys:
			del self._cooldowns[k]
