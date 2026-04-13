import io
import pytest
from unittest.mock import patch, MagicMock
from content.parser import ContentParser
from content.text_parser import parse_text
from content.pdf_parser import parse_pdf
from content.web_parser import parse_url


# --- parse_text ---

class TestParseText:
    def test_reads_string_content(self):
        file = io.StringIO("hello world")
        assert parse_text(file) == "hello world"

    def test_decodes_bytes_content(self):
        file = io.BytesIO(b"hello bytes")
        assert parse_text(file) == "hello bytes"

    def test_empty_file(self):
        file = io.StringIO("")
        assert parse_text(file) == ""

    def test_unicode_content(self):
        file = io.BytesIO("café résumé".encode("utf-8"))
        assert parse_text(file) == "café résumé"


# --- parse_pdf ---

class TestParsePdf:
    @patch("content.pdf_parser.pdfplumber.open")
    def test_extracts_text_from_pages(self, mock_open):
        page1 = MagicMock()
        page1.extract_text.return_value = "Page one text"
        page2 = MagicMock()
        page2.extract_text.return_value = "Page two text"

        mock_pdf = MagicMock()
        mock_pdf.pages = [page1, page2]
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_pdf

        file = io.BytesIO(b"fake pdf bytes")
        result = parse_pdf(file)
        assert result == "Page one text\n\nPage two text"

    @patch("content.pdf_parser.pdfplumber.open")
    def test_skips_pages_with_no_text(self, mock_open):
        page1 = MagicMock()
        page1.extract_text.return_value = "Has text"
        page2 = MagicMock()
        page2.extract_text.return_value = None

        mock_pdf = MagicMock()
        mock_pdf.pages = [page1, page2]
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_pdf

        file = io.BytesIO(b"fake pdf bytes")
        result = parse_pdf(file)
        assert result == "Has text"

    @patch("content.pdf_parser.pdfplumber.open")
    def test_raises_when_no_text_extracted(self, mock_open):
        page = MagicMock()
        page.extract_text.return_value = None

        mock_pdf = MagicMock()
        mock_pdf.pages = [page]
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_pdf

        file = io.BytesIO(b"fake pdf bytes")
        with pytest.raises(ValueError, match="No text could be extracted"):
            parse_pdf(file)


# --- parse_url ---

class TestParseUrl:
    @patch("content.web_parser.trafilatura.extract")
    @patch("content.web_parser.trafilatura.fetch_url")
    def test_extracts_web_content(self, mock_fetch, mock_extract):
        mock_fetch.return_value = "<html>content</html>"
        mock_extract.return_value = "Extracted article text"

        result = parse_url("https://example.com")
        assert result == "Extracted article text"
        mock_fetch.assert_called_once_with("https://example.com")

    @patch("content.web_parser.trafilatura.fetch_url")
    def test_raises_when_fetch_fails(self, mock_fetch):
        mock_fetch.return_value = None
        with pytest.raises(ValueError, match="Failed to fetch URL"):
            parse_url("https://bad-url.com")

    @patch("content.web_parser.trafilatura.extract")
    @patch("content.web_parser.trafilatura.fetch_url")
    def test_raises_when_extract_fails(self, mock_fetch, mock_extract):
        mock_fetch.return_value = "<html></html>"
        mock_extract.return_value = None
        with pytest.raises(ValueError, match="Failed to extract content"):
            parse_url("https://example.com")


# --- ContentParser dispatcher ---

class TestContentParser:
    @patch("content.parser.parse_url")
    def test_dispatches_string_to_url_parser(self, mock_parse_url):
        mock_parse_url.return_value = "web content"
        result = ContentParser.parse("https://example.com")
        assert result == "web content"
        mock_parse_url.assert_called_once_with("https://example.com")

    @patch("content.parser.parse_pdf")
    def test_dispatches_pdf_file(self, mock_parse_pdf):
        mock_parse_pdf.return_value = "pdf content"
        file = MagicMock()
        file.name = "document.pdf"
        result = ContentParser.parse(file)
        assert result == "pdf content"

    @patch("content.parser.parse_pdf")
    def test_dispatches_uppercase_pdf(self, mock_parse_pdf):
        mock_parse_pdf.return_value = "pdf content"
        file = MagicMock()
        file.name = "document.PDF"
        result = ContentParser.parse(file)
        assert result == "pdf content"

    @patch("content.parser.parse_text")
    def test_dispatches_text_file(self, mock_parse_text):
        mock_parse_text.return_value = "text content"
        file = MagicMock()
        file.name = "notes.txt"
        result = ContentParser.parse(file)
        assert result == "text content"

    @patch("content.parser.parse_text")
    def test_dispatches_non_pdf_file_to_text(self, mock_parse_text):
        mock_parse_text.return_value = "csv content"
        file = MagicMock()
        file.name = "data.csv"
        result = ContentParser.parse(file)
        assert result == "csv content"

    def test_raises_for_unsupported_type(self):
        with pytest.raises(ValueError, match="Unsupported source type"):
            ContentParser.parse(12345)

    @patch("content.parser.parse_url")
    @patch("content.parser.config")
    def test_truncates_to_max_context_length(self, mock_config, mock_parse_url):
        mock_config.MAX_CONTEXT_LENGTH = 10
        mock_parse_url.return_value = "a" * 100
        result = ContentParser.parse("https://example.com")
        assert len(result) == 10
