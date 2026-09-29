"""
Tests for pluggable PDF extractors (Docling, Mistral OCR, Landing AI).

Every extractor returns {"markdown": str, "metadata": {...}}, the shape the
FinancialMapper already parses.
"""

import base64

import pytest

from counterfactual_oracle.src.parsers.extractor import DocumentExtractor
from counterfactual_oracle.src.parsers.extractors import (
    DoclingExtractor,
    MistralOCRExtractor,
    create_extractor,
)
from counterfactual_oracle.src.parsers.mapper import FinancialMapper

INCOME_STATEMENT_MD = """
## Condensed Consolidated Statements of Income

| | Three Months Ended |
|---|---|
| Total net sales | 119,575 |
| Total cost of sales | 64,720 |
| Gross margin | 54,855 |
| Total operating expenses | 14,482 |
| Operating income | 40,373 |
"""


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "filing.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    return path


# --- Docling ------------------------------------------------------------------

class _FakeDoclingDocument:
    pages = {1: object(), 2: object()}

    def export_to_markdown(self):
        return INCOME_STATEMENT_MD


class _FakeConverter:
    def __init__(self):
        self.sources = []

    def convert(self, source):
        self.sources.append(source)

        class Result:
            document = _FakeDoclingDocument()

        return Result()


def test_docling_extractor_returns_markdown_and_page_count(pdf):
    converter = _FakeConverter()

    raw = DoclingExtractor(converter=converter).extract(str(pdf))

    assert converter.sources == [str(pdf)]
    assert raw["markdown"] == INCOME_STATEMENT_MD
    assert raw["metadata"]["page_count"] == 2
    assert raw["metadata"]["extractor"] == "docling"


def test_docling_markdown_tables_feed_existing_mapper(pdf):
    raw = DoclingExtractor(converter=_FakeConverter()).extract(str(pdf))

    report = FinancialMapper().parse_raw_response(raw)

    # "Three Months Ended" -> quarterly, annualized x4 by the mapper
    assert report.income_statement.Revenue == pytest.approx(119_575 * 4)
    assert report.income_statement.EBIT == pytest.approx(40_373 * 4)


# --- Mistral OCR ----------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = str(payload)

    def json(self):
        return self._payload


class _FakePost:
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status
        self.calls = []

    def __call__(self, url, headers, json, timeout):
        self.calls.append((url, headers, json))
        return _FakeResponse(self.payload, self.status)


def test_mistral_extractor_sends_base64_pdf_and_joins_pages(pdf):
    post = _FakePost({
        "pages": [{"index": 1, "markdown": "page two"}, {"index": 0, "markdown": "page one"}],
        "usage_info": {"pages_processed": 2},
    })

    raw = MistralOCRExtractor(api_key="k", post=post).extract(str(pdf))

    url, headers, body = post.calls[0]
    assert url == "https://api.mistral.ai/v1/ocr"
    assert headers["Authorization"] == "Bearer k"
    assert body["document"]["type"] == "document_url"
    assert body["document"]["document_url"] == (
        "data:application/pdf;base64," + base64.b64encode(pdf.read_bytes()).decode()
    )
    assert "table_format" not in body  # keep tables inline as markdown for the mapper
    assert raw["markdown"] == "page one\n\npage two"
    assert raw["metadata"] == {"page_count": 2, "extractor": "mistral"}


def test_mistral_extractor_raises_on_http_error(pdf):
    with pytest.raises(RuntimeError, match="401"):
        MistralOCRExtractor(api_key="bad", post=_FakePost({"detail": "unauthorized"}, 401)).extract(str(pdf))


def test_mistral_extractor_requires_api_key():
    with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
        MistralOCRExtractor(api_key="")


# --- factory ------------------------------------------------------------------

def test_create_extractor_by_name():
    assert isinstance(create_extractor("docling", converter=_FakeConverter()), DoclingExtractor)
    assert isinstance(create_extractor("mistral", mistral_api_key="k"), MistralOCRExtractor)
    assert isinstance(create_extractor("landing_ai"), DocumentExtractor)


def test_create_extractor_rejects_unknown_name():
    with pytest.raises(ValueError, match="unknown extractor"):
        create_extractor("tesseract")


# --- wiring into the clients ------------------------------------------------------

class _StaticExtractor:
    def __init__(self):
        self.paths = []

    def extract(self, pdf_path):
        self.paths.append(pdf_path)
        return {"markdown": INCOME_STATEMENT_MD, "metadata": {"page_count": 1}}


def test_streamlit_client_uses_injected_extractor(pdf):
    from counterfactual_oracle.src.agents.landing_ai import LandingAIClient

    extractor = _StaticExtractor()
    report = LandingAIClient(api_key="", extractor=extractor).extract_data(str(pdf))

    assert extractor.paths == [str(pdf)]
    assert report.income_statement.Revenue > 0


def test_refactored_client_uses_injected_extractor(pdf):
    from counterfactual_oracle.src.agents.landing_ai_refactored import LandingAIClient

    extractor = _StaticExtractor()
    client = LandingAIClient(extractor=extractor)

    assert client.extractor is extractor
