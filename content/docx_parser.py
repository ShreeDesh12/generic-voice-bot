import logging
from docx import Document

logger = logging.getLogger(__name__)


def parse_docx(file) -> str:
    """Extract text from a DOCX file.

    Args:
        file: A file-like object or path to a .docx file.

    Returns:
        Extracted text with paragraphs separated by newlines.

    Raises:
        ValueError: If no text could be extracted.
    """
    logger.info("Parsing DOCX file")
    doc = Document(file)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        raise ValueError("No text extracted from DOCX file.")
    text = "\n".join(paragraphs)
    logger.info("Extracted %d characters from DOCX", len(text))
    return text
