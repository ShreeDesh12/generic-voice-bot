import io
import logging
import pdfplumber

logger = logging.getLogger(__name__)


def parse_pdf(file) -> str:
    """Extract text from an uploaded PDF file."""
    logger.info("Parsing PDF file")
    pdf_bytes = file.read()
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        logger.info("PDF has %d pages", len(pdf.pages))
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
            else:
                logger.debug("Page %d: no text extracted", i + 1)
    if not text_parts:
        logger.error("No text could be extracted from PDF")
        raise ValueError("No text could be extracted from the PDF.")
    logger.info("Extracted text from %d/%d pages", len(text_parts), len(pdf.pages))
    return "\n\n".join(text_parts)
