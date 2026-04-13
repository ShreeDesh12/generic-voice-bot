def parse_text(file) -> str:
    """Extract text from an uploaded text file."""
    content = file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    return content
