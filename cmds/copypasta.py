import random
import re

def handle_copypasta_command(reference):
    if reference is None or not reference.resolved.content:
        return "You need to reply to a message to use this command."

    EMOJIS = ["😂", "👌", "✌", "💞", "👍", "💯", "👀", "👓", "👏",
              "👐", "🍕", "💥", "🍴", "💦", "🍑", "🍆", "😩", "😏",
              "👉👌", "👅", "🚰"]

    text = reference.resolved.content
    user_tags = re.finditer(r'<@!?\d+>', text)
    tag_positions = [(m.start(), m.end(), m.group()) for m in user_tags]

    working_text = re.sub(r'<@!?\d+>', '', text)
    b_char = random.choice(working_text.lower())

    result = []
    for char in working_text:
        if char == " ":
            result.append(" " + random.choice(EMOJIS) + " ")
        elif char in EMOJIS:
            result.append(char + random.choice(EMOJIS))
        elif char.lower() == b_char:
            result.append("🅱️")
        else:
            result.append(char.upper() if random.getrandbits(1) else char.lower())

    final_result = [random.choice(EMOJIS) + " "]
    current_pos = 0
    result_text = ''.join(result)

    for start, end, tag in tag_positions:
        final_result.append(result_text[current_pos:start])
        final_result.append(tag + " ")
        current_pos = start

    final_result.append(result_text[current_pos:])
    final_result.append(" " + random.choice(EMOJIS))

    return ''.join(final_result)
