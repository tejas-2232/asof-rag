import hashlib
import re
import uuid
from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag

from .models import Chunk, Filing

SPACE = re.compile(r"\s+")
ITEM = re.compile(r"^(item\s+\d+[a-z]?(?:\s*[.:—-].*)?)$", re.IGNORECASE)
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


def normalize_text(value: str) -> str:
    return SPACE.sub(" ", value).strip()


def sha256(value: bytes | str) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def filing_content_hash(html: bytes) -> str:
    return sha256(html)


def _section_blocks(html: bytes) -> Iterable[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    for unwanted in soup(["script", "style", "noscript", "nav"]):
        unwanted.decompose()

    section = "Document"
    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "td"]):
        if not isinstance(element, Tag):
            continue
        if element.name == "div" and element.find(["p", "div", "table"]):
            continue
        if element.name == "td" and element.find(["p", "div"]):
            continue
        if element.find_parent("p"):
            continue
        text = normalize_text(element.get_text(" ", strip=True))
        if not text:
            continue
        is_heading = element.name in HEADINGS or (
            len(text) <= 160 and ITEM.match(text) is not None
        )
        if is_heading:
            section = text[:200]
        else:
            yield section, text


def parse_filing(html: bytes, filing: Filing, max_chars: int = 1_600) -> list[Chunk]:
    grouped: list[tuple[str, str]] = []
    current_section = ""
    buffer = ""

    for section, block in _section_blocks(html):
        if section != current_section or len(buffer) + len(block) + 1 > max_chars:
            if buffer:
                grouped.append((current_section, buffer))
            current_section, buffer = section, block
        else:
            buffer = f"{buffer}\n{block}" if buffer else block
    if buffer:
        grouped.append((current_section, buffer))

    filing_id = filing.accession
    chunks: list[Chunk] = []
    for ordinal, (section, text) in enumerate(grouped):
        content_hash = sha256(text)
        chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{filing_id}:{ordinal}:{content_hash}"))
        chunks.append(
            Chunk(
                id=chunk_id,
                filing_id=filing_id,
                ticker=filing.ticker,
                cik=filing.cik,
                accession=filing.accession,
                form=filing.form,
                report_date=filing.report_date,
                filed_at=filing.filed_at,
                filed_at_epoch=int(filing.filed_at.timestamp()),
                source_url=filing.source_url,
                content_hash=content_hash,
                filing_content_hash=filing.content_hash,
                version=filing.version,
                parent_content_hash=filing.parent_content_hash,
                section=section,
                ordinal=ordinal,
                text=text,
            )
        )
    return chunks
