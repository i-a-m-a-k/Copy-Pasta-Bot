import random
import re

def handle_stretch_command(reference):
    if reference is None or not reference.resolved.content:
        return "You need to reply to a message to use this command."

    text = reference.resolved.content
    user_tags = re.finditer(r'<@!?\d+>', text)
    tag_positions = [(m.start(), m.end(), m.group()) for m in user_tags]

    working_text = re.sub(r'<@!?\d+>', '', text)
    count = random.randint(3, 10)
    result = re.sub(r'([aeiouAEIOUａｅｉｏｕＡＥＩＯＵ])',
                   lambda m: m.group(1) * count, working_text)

    final_result = []
    current_pos = 0
    for start, end, tag in tag_positions:
        final_result.append(result[current_pos:start])
        final_result.append(tag)
        current_pos = start

    final_result.append(result[current_pos:])
    return ''.join(final_result)
