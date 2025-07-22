def handle_clap_command(reply):
    if not reply.resolved.content:
        return "Cannot clap an empty message or a message with only attachments."

    # Split keeping whitespace to preserve formatting
    parts = reply.resolved.content.split(' ')
    # Filter out empty strings but keep whitespace for formatting
    parts = [part if part.strip() else ' ' for part in parts]
    # Join non-empty parts with clap emoji
    return ' 👏 '.join(p for p in parts if p.strip())
