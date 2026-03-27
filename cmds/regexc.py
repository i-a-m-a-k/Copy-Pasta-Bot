import constants

import re
import shlex

def replace_curly_quotes(s: str) -> str:
    QUOTE_MAP = {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
    }
    return s.translate(str.maketrans(QUOTE_MAP))


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
		result = re.sub(pattern, replacement, string, count=count, flags=flags)
	except re.error as e:
		return f"Invalid regex pattern: `{e}`"

	if result == string:
		return constants.REGEX_NOT_FOUND

	return result