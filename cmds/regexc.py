import constants

import re
import shlex
import threading

# Safety limits for user-supplied regex
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
	"""Run re.sub in a daemon thread with a timeout to prevent ReDoS.

	Returns (result, error_message).  On success error_message is None.
	On timeout or regex error, result is None and error_message is set.
	"""
	result = [None]
	error = [None]

	def worker():
		try:
			result[0] = re.sub(pattern, replacement, string,
			                   count=count, flags=flags)
		except re.error as e:
			error[0] = e

	thread = threading.Thread(target=worker, daemon=True)
	thread.start()
	thread.join(timeout=timeout)

	if thread.is_alive():
		# Thread is still running – catastrophic backtracking detected.
		# Daemon thread will be cleaned up on process exit.
		return None, ("Regex timed out (possible catastrophic backtracking). "
		              "Try a simpler pattern.")

	if error[0]:
		return None, f"Invalid regex pattern: `{error[0]}`"

	return result[0], None


def handle_regex(args: list, reply):
	if reply is None:
		return constants.REGEX_NO_REPLY

	if not reply.resolved.content:
		return constants.REGEX_EMPTY_MSG

	if len(args) < 3:
		return constants.REGEX_USAGE

	try:
		raw = replace_curly_quotes(" ".join(args[1:]))
		parts = shlex.split(raw)
	except ValueError as e:
		return f"Parsing error: `{e}`"

	if len(parts) < 2:
		return constants.REGEX_USAGE

	pattern, replacement, *rest = parts
	flags_str = rest[0] if rest else ""

	# Reject excessively long patterns to reduce ReDoS surface
	if len(pattern) > MAX_PATTERN_LENGTH:
		return f"Pattern too long (max {MAX_PATTERN_LENGTH} characters)."

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

	# Pre-validate the pattern before running the timed substitution
	try:
		re.compile(pattern, flags)
	except re.error as e:
		return f"Invalid regex pattern: `{e}`"

	# Run substitution with timeout protection
	result, error_msg = _regex_sub_with_timeout(
		pattern, replacement, string, count, flags
	)

	if error_msg:
		return error_msg

	if result == string:
		return constants.REGEX_NOT_FOUND

	return result