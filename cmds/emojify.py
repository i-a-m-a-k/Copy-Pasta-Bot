import re

def handle_emojify_command(reply):
    if reply is None:
        return "You need to reply to a message to use this command."
    
    text = reply.resolved.content
    if not text:
        return "Message has no text content to emojify."

    # Regex patterns for things to preserve as-is
    # Discord user/role mentions: <@123> or <@!123> or <@&123>
    # Discord channel mentions: <#123>
    # Discord custom emojis: <:name:123> or <a:name:123>
    # URLs
    preserve_pattern = re.compile(
        r'(<@!?\d+>|<@&\d+>|<#\d+>|<a?:\w+:\d+>|https?://\S+)'
    )

    # Split text into preserved tokens and normal text
    parts = preserve_pattern.split(text)
    result_parts = []

    for part in parts:
        if preserve_pattern.match(part):
            # Keep Discord mentions, emojis, and URLs as-is
            result_parts.append(part)
        else:
            # Emojify normal text
            emojified = []
            for char in part.lower():
                if 'a' <= char <= 'z':
                    # Regional indicator symbols: U+1F1E6 ('a') to U+1F1FF ('z')
                    emojified.append(chr(0x1F1E6 + ord(char) - ord('a')))
                elif '0' <= char <= '9':
                    num_emojis = ['0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
                    emojified.append(num_emojis[int(char)])
                elif char == ' ':
                    emojified.append('   ')  # Triple space for word gaps
                elif char == '?':
                    emojified.append('❓')
                elif char == '!':
                    emojified.append('❗')
                else:
                    emojified.append(char)
            # Always space between regional indicators to prevent country flag rendering
            result_parts.append(' '.join(emojified))

    return ' '.join(result_parts)
