from __future__ import annotations

import re

from bs4 import BeautifulSoup


# Common signature delimiters
SIGNATURE_PATTERNS = [
    re.compile(r"^--\s*$", re.MULTILINE),
    re.compile(r"^Sent from my (iPhone|iPad|Galaxy|Android)", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Get Outlook for", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^_{3,}$", re.MULTILINE),
]

# Quoted reply patterns
QUOTE_PATTERNS = [
    re.compile(r"^On .+ wrote:$", re.MULTILINE),
    re.compile(r"^>+ ", re.MULTILINE),
    re.compile(r"^-{3,} ?Original Message ?-{3,}", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^-{3,} ?Forwarded message ?-{3,}", re.MULTILINE | re.IGNORECASE),
]


def html_to_text(html: str) -> str:
    """
    Convert HTML email body to clean plain text.

    Preserves semantic structure: headings become bold-style markers,
    lists get bullet points, links retain their URLs.
    """
    if not html.strip():
        return ""

    soup = BeautifulSoup(html, "lxml")

    # Remove non-content elements
    for tag in soup.find_all(["script", "style", "head", "meta", "link"]):
        tag.decompose()

    # Convert links to "text (url)" format
    for a_tag in soup.find_all("a"):
        href = a_tag.get("href", "")
        text = a_tag.get_text(strip=True)
        if href and text and href != text:
            a_tag.replace_with(f"{text} ({href})")
        elif text:
            a_tag.replace_with(text)

    # Convert list items
    for li in soup.find_all("li"):
        li.insert_before("\n- ")

    # Convert headings
    for level in range(1, 7):
        for heading in soup.find_all(f"h{level}"):
            text = heading.get_text(strip=True)
            heading.replace_with(f"\n{text}\n")

    # Convert <br> to newlines
    for br in soup.find_all("br"):
        br.replace_with("\n")

    # Convert <p> to double newlines
    for p in soup.find_all("p"):
        p.insert_after("\n\n")

    # Get text and clean up whitespace
    text = soup.get_text()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def clean_email_body(text: str, strip_signatures: bool = True, strip_quotes: bool = False) -> str:
    """
    Clean an email body text.

    Args:
        text: Raw email body text.
        strip_signatures: Remove email signatures.
        strip_quotes: Remove quoted replies (On ... wrote:).
    """
    if not text:
        return ""

    if strip_signatures:
        text = _strip_signatures(text)

    if strip_quotes:
        text = _strip_quoted_replies(text)

    # Normalize whitespace
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text


def get_clean_body(body_text: str, body_html: str) -> str:
    """
    Get the best available clean text body from an email.
    Prefers plain text if available, falls back to HTML conversion.
    """
    if body_text.strip():
        return clean_email_body(body_text)

    if body_html.strip():
        converted = html_to_text(body_html)
        return clean_email_body(converted)

    return ""


def _strip_signatures(text: str) -> str:
    """Remove email signatures from text."""
    lines = text.split("\n")
    cut_index = len(lines)

    for i, line in enumerate(lines):
        for pattern in SIGNATURE_PATTERNS:
            if pattern.search(line):
                # Only cut if it's in the last ~30% of the email
                if i > len(lines) * 0.7:
                    cut_index = i
                    break
        if cut_index < len(lines):
            break

    return "\n".join(lines[:cut_index])


def _strip_quoted_replies(text: str) -> str:
    """Remove quoted reply sections from text."""
    lines = text.split("\n")
    cut_index = len(lines)

    for i, line in enumerate(lines):
        for pattern in QUOTE_PATTERNS:
            if pattern.search(line):
                cut_index = i
                break
        if cut_index < len(lines):
            break

    return "\n".join(lines[:cut_index])
