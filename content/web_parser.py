import logging
import re
import requests
import trafilatura

logger = logging.getLogger(__name__)

# Patterns that indicate a portfolio or professional profile page
_PORTFOLIO_PATTERNS = [
    r"linkedin\.com/in/",
    r"github\.com/",
    r"behance\.net/",
    r"dribbble\.com/",
    r"portfolio",
    r"about\s*me",
    r"resume",
    r"cv",
    r"personal",
    r"\.dev$",
    r"\.me$",
    r"\.io/",
    r"carrd\.co/",
    r"wixsite\.com/",
    r"webflow\.io/",
    r"squarespace\.com/",
    r"wordpress\.com/",
    r"sites\.google\.com/",
    r"buildwith",
]

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}"
)
_LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[\w\-]+/?")

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def _is_linkedin_url(url: str) -> bool:
    """Check if the URL is a LinkedIn profile."""
    return bool(re.search(r"linkedin\.com/in/", url.lower()))


def _is_portfolio_url(url: str) -> bool:
    """Check if the URL looks like a portfolio or professional profile."""
    url_lower = url.lower()
    for pattern in _PORTFOLIO_PATTERNS:
        if re.search(pattern, url_lower):
            return True
    return False


def _is_portfolio_content(text: str) -> bool:
    """Check if the extracted content looks like a portfolio page."""
    text_lower = text.lower()
    # Strong indicators — professional/personal portfolio content
    indicators = [
        "experience",
        "education",
        "skills",
        "projects",
        "contact",
        "about me",
        "about",
        "work history",
        "resume",
        "portfolio",
        "certifications",
        "achievements",
        "hire me",
        "get in touch",
        "let's connect",
        "worked at",
        "freelance",
        "developer",
        "designer",
        "engineer",
        "built with",
        "technologies",
        "tech stack",
    ]
    matches = sum(1 for ind in indicators if ind in text_lower)
    # Also check if there's an email — strong signal for a personal site
    has_email = bool(_EMAIL_RE.search(text))
    return matches >= 2 or (matches >= 1 and has_email)


def extract_contact_details(text: str, url: str) -> dict:
    """Extract contact details from parsed portfolio text."""
    contacts = {}

    emails = _EMAIL_RE.findall(text)
    if emails:
        contacts["email"] = emails[0]

    phones = _PHONE_RE.findall(text)
    if phones:
        # Filter out unlikely phone numbers (too short)
        valid_phones = [p.strip() for p in phones if len(re.sub(r"\D", "", p)) >= 7]
        if valid_phones:
            contacts["phone"] = valid_phones[0]

    linkedin_urls = _LINKEDIN_RE.findall(text)
    if linkedin_urls:
        contacts["linkedin"] = linkedin_urls[0]
    elif "linkedin.com/in/" in url:
        contacts["linkedin"] = url

    return contacts


def _fetch_with_headers(url: str) -> str:
    """Fetch a URL using browser-like headers (handles sites that block bots)."""
    logger.info("Fetching URL with browser headers: %s", url)
    resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def _parse_linkedin(url: str) -> str:
    """Fetch and extract content from a LinkedIn profile.

    LinkedIn blocks simple fetches, so we use browser-like headers
    and fall back to extracting from the raw HTML meta/structured data.
    """
    logger.info("Parsing LinkedIn profile: %s", url)
    html = _fetch_with_headers(url)

    # First try trafilatura on the fetched HTML
    text = trafilatura.extract(html)
    if text and len(text) > 100:
        logger.info("Trafilatura extracted %d chars from LinkedIn", len(text))
        return text

    # Fallback: extract from meta tags and visible text in the HTML
    # LinkedIn public profiles embed structured info in meta tags
    parts = []

    # og:title usually has the name + headline
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    if title_match:
        parts.append(title_match.group(1).strip())

    # Meta description often has a summary
    desc_match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if not desc_match:
        desc_match = re.search(
            r'<meta\s+content=["\']([^"\']+)["\']\s+name=["\']description["\']',
            html,
            re.IGNORECASE,
        )
    if desc_match:
        parts.append(desc_match.group(1).strip())

    # og:description
    og_desc = re.search(
        r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if not og_desc:
        og_desc = re.search(
            r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:description["\']',
            html,
            re.IGNORECASE,
        )
    if og_desc:
        desc_text = og_desc.group(1).strip()
        if desc_text not in "\n".join(parts):
            parts.append(desc_text)

    # Extract any JSON-LD structured data (LinkedIn sometimes includes this)
    json_ld_matches = re.findall(
        r'<script\s+type=["\']application/ld\+json["\']\s*>([^<]+)</script>',
        html,
        re.IGNORECASE,
    )
    for json_str in json_ld_matches:
        # Just include the raw text — the LLM can interpret it
        cleaned = re.sub(r'[{}\[\]"\\]', " ", json_str)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) > 50:
            parts.append(cleaned)

    if not parts:
        raise ValueError(
            f"Failed to extract content from LinkedIn profile: {url}. "
            "LinkedIn may require sign-in to view this profile."
        )

    result = "\n\n".join(parts)
    logger.info("Extracted %d chars from LinkedIn via meta/structured data", len(result))
    return result


def parse_url(url: str) -> str:
    """Extract main content from a web page URL."""
    logger.info("Fetching URL: %s", url)

    if _is_linkedin_url(url):
        return _parse_linkedin(url)

    # Try trafilatura first (default path)
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        # Fallback: try with browser headers
        logger.warning("trafilatura failed for %s, trying with browser headers", url)
        try:
            html = _fetch_with_headers(url)
            text = trafilatura.extract(html)
            if text:
                logger.info("Extracted %d characters from %s (via headers fallback)", len(text), url)
                return text
        except Exception as e:
            logger.error("Browser headers fallback also failed for %s: %s", url, e)
        raise ValueError(f"Failed to fetch URL: {url}")

    text = trafilatura.extract(downloaded)
    if text is None:
        logger.error("Failed to extract content from: %s", url)
        raise ValueError(f"Failed to extract content from: {url}")
    logger.info("Extracted %d characters from %s", len(text), url)
    return text


def parse_portfolio_url(url: str) -> tuple[str, dict]:
    """Parse a portfolio URL, validate it, and extract contact details.

    Returns:
        Tuple of (extracted_text, contact_details_dict).

    Raises:
        ValueError: If the URL doesn't appear to be a portfolio site.
    """
    if not _is_portfolio_url(url):
        # Fetch content first and check if it looks like a portfolio
        try:
            text = parse_url(url)
        except ValueError:
            raise ValueError(
                "Website seems fishy! Please provide your portfolio link to help you."
            )

        if not _is_portfolio_content(text):
            raise ValueError(
                "Website seems fishy! Please provide your portfolio link to help you."
            )
    else:
        text = parse_url(url)

    contacts = extract_contact_details(text, url)
    logger.info("Extracted contact details: %s", contacts)
    return text, contacts
