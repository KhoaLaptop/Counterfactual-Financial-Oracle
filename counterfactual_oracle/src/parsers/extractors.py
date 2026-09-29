"""
Pluggable PDF extractors.

Each extractor returns {"markdown": str, "metadata": {...}}: the shape
FinancialMapper.parse_raw_response already parses (markdown and HTML tables).

- docling     Local and free (IBM Docling). Default.
- mistral     Mistral OCR API, ~$4 per 1,000 pages. Good on scanned PDFs.
- landing_ai  Landing AI ADE (the original extractor).
"""

import base64
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol

from ..config import settings
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)

MISTRAL_OCR_URL = "https://api.mistral.ai/v1/ocr"


class Extractor(Protocol):
    def extract(self, pdf_path: str) -> Dict[str, Any]: ...


class DoclingExtractor:
    """Runs IBM Docling locally: layout analysis + TableFormer table structure."""

    def __init__(self, converter=None):
        if converter is None:
            from docling.document_converter import DocumentConverter  # heavy import, load on use

            converter = DocumentConverter()
        self.converter = converter

    def extract(self, pdf_path: str) -> Dict[str, Any]:
        logger.info("docling_extraction_started", file_path=pdf_path)
        document = self.converter.convert(pdf_path).document
        return {
            "markdown": document.export_to_markdown(),
            "metadata": {"page_count": len(document.pages), "extractor": "docling"},
        }


class MistralOCRExtractor:
    """Mistral OCR API. Tables are returned inline as markdown."""

    def __init__(
        self,
        api_key: str,
        model: str = "mistral-ocr-latest",
        post: Optional[Callable] = None,
        timeout: int = 300,
    ):
        if not api_key:
            raise ValueError("Mistral OCR needs an API key: set MISTRAL_API_KEY")
        if post is None:
            import requests

            post = requests.post
        self.api_key, self.model, self.post, self.timeout = api_key, model, post, timeout

    def extract(self, pdf_path: str) -> Dict[str, Any]:
        encoded = base64.b64encode(Path(pdf_path).read_bytes()).decode()
        response = self.post(
            MISTRAL_OCR_URL,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "document": {"type": "document_url", "document_url": f"data:application/pdf;base64,{encoded}"},
            },
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Mistral OCR error {response.status_code}: {response.text[:500]}")

        pages = sorted(response.json().get("pages", []), key=lambda p: p.get("index", 0))
        return {
            "markdown": "\n\n".join(p.get("markdown", "") for p in pages),
            "metadata": {"page_count": len(pages), "extractor": "mistral"},
        }


def create_extractor(name: Optional[str] = None, **kwargs) -> Extractor:
    """Build the extractor named by `name` (default: settings.document_extractor)."""
    name = (name or settings.document_extractor).lower()
    if name == "docling":
        return DoclingExtractor(converter=kwargs.get("converter"))
    if name == "mistral":
        return MistralOCRExtractor(api_key=kwargs.get("mistral_api_key", settings.mistral_api_key))
    if name == "landing_ai":
        from .extractor import DocumentExtractor

        return DocumentExtractor()
    raise ValueError(f"unknown extractor {name!r}: use docling, mistral or landing_ai")
