import random
import re

def handle_owo_command(reference):
    if reference is None or not reference.resolved.content:
        return "You need to reply to a message to use this command."

    FACES = ['(・`ω´・)', ';;w;;', 'owo', 'UwU', '>w<', '^w^', r'\(^o\) (/o^)/',
             '( ^ _ ^)∠☆', '(ô_ô)', '~:o', ';____;', '(*^*)', '(>_',
             '(♥_♥)', '*(^O^)*', '((+_+))']

    text = reference.resolved.content
    user_tags = re.finditer(r'<@!?\d+>', text)
    tag_positions = [(m.start(), m.end(), m.group()) for m in user_tags]
    working_text = re.sub(r'<@!?\d+>', '', text)
    result = working_text

    result = re.sub(r'[rl]', "w", result)
    result = re.sub(r'[ｒｌ]', "ｗ", result)
    result = re.sub(r'[RL]', 'W', result)
    result = re.sub(r'[ＲＬ]', 'Ｗ', result)
    result = re.sub(r'n([aeiouａｅｉｏｕ])', r'ny\1', result)
    result = re.sub(r'ｎ([ａｅｉｏｕ])', r'ｎｙ\1', result)
    result = re.sub(r'N([aeiouAEIOU])', r'Ny\1', result)
    result = re.sub(r'Ｎ([ａｅｉｏｕＡＥＩＯＵ])', r'Ｎｙ\1', result)
    result = re.sub(r'\!+', ' ' + random.choice(FACES), result)
    result = re.sub(r'！+', ' ' + random.choice(FACES), result)
    result = result.replace("ove", "uv")
    result = result.replace("ｏｖｅ", "ｕｖ")

    final_result = []
    current_pos = 0
    for start, end, tag in tag_positions:
        final_result.append(result[current_pos:start])
        final_result.append(tag)
        current_pos = start

    final_result.append(result[current_pos:])
    final_result.append(' ' + random.choice(FACES))

    return ''.join(final_result)
