import constants
import re
import shlex
import threading
from typing import Union
import discord
from ui.embeds import error_embed, warning_embed, info_embed

MAX_PATTERN_LENGTH = 200
REGEX_TIMEOUT_SECONDS = 2

def replace_curly_quotes(s: str) -> str:
    QUOTE_MAP = {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
    }
    return s.translate(str.maketrans(QUOTE_MAP))

def _regex_sub_with_timeout(pattern, replacement, string, count, flags,
                            timeout=REGEX_TIMEOUT_SECONDS):
	"""Run re.sub in a daemon thread with a timeout to prevent ReDoS."""
	result = [None]
	error = [None]

	def worker():
		try:
			result[0] = re.sub(pattern, replacement, string, count=count, flags=flags)
		except re.error as e:
			error[0] = e

	thread = threading.Thread(target=worker, daemon=True)
	thread.start()
	thread.join(timeout=timeout)

	if thread.is_alive():
		return None, ("Regex timed out (possible catastrophic backtracking). "
		              "Try a simpler pattern.")

	if error[0]:
		return None, f"Invalid regex pattern: `{error[0]}`"

	return result[0], None

def handle_regex(args: list, reply) -> Union[str, discord.Embed]:
	if reply is None:
		return warning_embed(constants.REGEX_NO_REPLY, title="⚠️ No Reply Target")

	if not reply.resolved.content:
		return warning_embed(constants.REGEX_EMPTY_MSG, title="⚠️ Empty Message")

	if len(args) < 3:
		return info_embed(constants.REGEX_USAGE, title="📝 Regex Usage")

	try:
		raw = replace_curly_quotes(" ".join(args[1:]))
		parts = shlex.split(raw)
	except ValueError as e:
		return error_embed(f"Parsing error: `{e}`", title="❌ Parse Error")

	if len(parts) < 2:
		return info_embed(constants.REGEX_USAGE, title="📝 Regex Usage")

	pattern, replacement, *rest = parts
	flags_str = rest[0] if rest else ""

	if len(pattern) > MAX_PATTERN_LENGTH:
		return error_embed(
			f"Pattern too long (max {MAX_PATTERN_LENGTH} characters).",
			title="❌ Pattern Too Long"
		)

	flags = 0
	count = 1

	flags_set = set(flags_str)
	digits = re.search(r"\d+", flags_str)

	if "g" in flags_set:
		count = 0
	if digits:
		count = int(digits.group())
	if "i" in flags_set:
		flags |= re.IGNORECASE

	string = reply.resolved.content

	try:
		re.compile(pattern, flags)
	except re.error as e:
		return error_embed(f"Invalid regex pattern: `{e}`", title="❌ Invalid Pattern")

	result, error_msg = _regex_sub_with_timeout(
		pattern, replacement, string, count, flags
	)

	if error_msg:
		return error_embed(error_msg, title="❌ Regex Error")

	if result == string:
		return info_embed(constants.REGEX_NOT_FOUND, title="🔍 No Match")

	return result
