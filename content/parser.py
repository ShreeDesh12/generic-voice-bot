import re
from content.text_parser import parse_text
from content.web_parser import parse_url, parse_portfolio_url, extract_contact_details, _EMAIL_RE
from content.pdf_parser import parse_pdf
from content.docx_parser import parse_docx
import config


_RESUME_INDICATORS = [
    "experience",
    "education",
    "skills",
    "projects",
    "contact",
    "objective",
    "summary",
    "work history",
    "resume",
    "certifications",
    "achievements",
    "references",
    "proficiency",
    "employment",
    "qualification",
]


def _is_resume_content(text: str) -> bool:
    """Check if the text looks like a resume."""
    text_lower = text.lower()
    matches = sum(1 for ind in _RESUME_INDICATORS if ind in text_lower)
    return matches >= 2


def _extract_name_from_resume(text: str) -> str:
    """Try to extract the person's name from the first few lines of a resume.

    Resumes typically have the name as the first non-empty line.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return "Unknown"

    # First line is usually the name
    candidate = lines[0]

    # Skip if it looks like a section header or too long
    if len(candidate) > 50 or any(
        kw in candidate.lower()
        for kw in ["resume", "curriculum", "objective", "summary", "http"]
    ):
        # Try second line
        if len(lines) > 1 and len(lines[1]) < 50:
            candidate = lines[1]
        else:
            return "Unknown"

    # Strip common prefixes
    candidate = re.sub(r"^(name|mr\.?|ms\.?|mrs\.?|dr\.?)\s*:?\s*", "", candidate, flags=re.IGNORECASE).strip()

    # Should look like a name (2-4 words, mostly alpha)
    words = candidate.split()
    if 1 <= len(words) <= 5 and all(re.match(r"^[A-Za-z.\-']+$", w) for w in words):
        return candidate

    return "Unknown"


class ContentParser:
    """Dispatcher that detects input type and delegates to the appropriate parser."""

    @staticmethod
    def parse(source) -> str:
        """Parse content from a URL string or uploaded file.

        Args:
            source: A URL string, or a file-like object (PDF, DOCX, or text).

        Returns:
            Extracted text, truncated to MAX_CONTEXT_LENGTH.
        """
        if isinstance(source, str):
            text = parse_url(source)
        elif hasattr(source, "name"):
            name_lower = source.name.lower()
            if name_lower.endswith(".pdf"):
                text = parse_pdf(source)
            elif name_lower.endswith(".docx"):
                text = parse_docx(source)
            else:
                text = parse_text(source)
        else:
            raise ValueError(f"Unsupported source type: {type(source)}")

        return text[: config.MAX_CONTEXT_LENGTH]

    @staticmethod
    def parse_portfolio(url: str) -> tuple[str, dict]:
        """Parse a portfolio URL and extract contact details."""
        text, contacts = parse_portfolio_url(url)
        return text[: config.MAX_CONTEXT_LENGTH], contacts

    @staticmethod
    def parse_resume(file) -> tuple[str, dict, str]:
        """Parse a resume file and extract contact details + name.

        Args:
            file: A file-like object (PDF, DOCX, or text).

        Returns:
            Tuple of (text, contact_details, extracted_name).

        Raises:
            ValueError: If the file doesn't look like a resume.
        """
        name_lower = file.filename.lower() if hasattr(file, "filename") else getattr(file, "name", "").lower()

        if name_lower.endswith(".pdf"):
            text = parse_pdf(file)
        elif name_lower.endswith(".docx"):
            text = parse_docx(file)
        else:
            text = parse_text(file)

        if not _is_resume_content(text):
            raise ValueError("This doesn't look like a resume. Please upload a valid resume (PDF or DOCX).")

        contacts = extract_contact_details(text, "")
        person_name = _extract_name_from_resume(text)

        return text[: config.MAX_CONTEXT_LENGTH], contacts, person_name
