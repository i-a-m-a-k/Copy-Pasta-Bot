def handle_vaporwave_command(reply):
    if reply is None:
        return "You need to reply to a message to use this command."
    
    text = reply.resolved.content
    if not text:
        return "Message has no text content to vaporwave."

    result = []
    for char in text:
        # Convert ASCII printable characters (0x21-0x7E) to fullwidth (0xFF01-0xFF5E)
        code = ord(char)
        if 0x21 <= code <= 0x7E:
            result.append(chr(code + 0xFEE0))
        elif char == ' ':
            result.append('\u3000')  # Fullwidth space
        else:
            result.append(char)
    
    return ''.join(result)
