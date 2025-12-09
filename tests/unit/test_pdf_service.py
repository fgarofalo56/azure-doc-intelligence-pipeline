"""Unit tests for the PDF service."""

import io
from unittest.mock import MagicMock, patch

import pytest
from pypdf import PdfWriter

from services.pdf_service import FormBoundary, PdfService


def create_test_pdf(num_pages: int) -> bytes:
    """Create a test PDF with specified number of pages."""
    writer = PdfWriter()
    for i in range(num_pages):
        writer.add_blank_page(width=612, height=792)  # Letter size

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output.read()


class TestPdfSplitError:
    """Tests for PdfSplitError exception."""

    def test_error_creation(self):
        """Test PdfSplitError creation."""
        from src.functions.services.pdf_service import PdfSplitError

        error = PdfSplitError("Test error")

        assert error.reason == "Test error"
        assert "PDF split failed" in str(error)
        assert "Test error" in str(error)


class TestPdfService:
    """Tests for PdfService class."""

    @pytest.fixture
    def pdf_service(self):
        """Create a PdfService instance with default settings."""
        from src.functions.services.pdf_service import PdfService

        return PdfService(pages_per_form=2)

    @pytest.fixture
    def single_page_pdf(self):
        """Create a 1-page test PDF."""
        return create_test_pdf(1)

    @pytest.fixture
    def two_page_pdf(self):
        """Create a 2-page test PDF."""
        return create_test_pdf(2)

    @pytest.fixture
    def six_page_pdf(self):
        """Create a 6-page test PDF."""
        return create_test_pdf(6)

    @pytest.fixture
    def five_page_pdf(self):
        """Create a 5-page test PDF (odd number for edge case)."""
        return create_test_pdf(5)

    def test_init(self, pdf_service):
        """Test initialization."""
        assert pdf_service.pages_per_form == 2

    def test_init_custom_pages(self):
        """Test initialization with custom pages per form."""
        from src.functions.services.pdf_service import PdfService

        service = PdfService(pages_per_form=4)
        assert service.pages_per_form == 4

    def test_get_page_count(self, pdf_service, six_page_pdf):
        """Test getting page count."""
        count = pdf_service.get_page_count(six_page_pdf)
        assert count == 6

    def test_get_page_count_single_page(self, pdf_service, single_page_pdf):
        """Test getting page count for single page PDF."""
        count = pdf_service.get_page_count(single_page_pdf)
        assert count == 1

    def test_get_page_count_invalid_pdf(self, pdf_service):
        """Test error on invalid PDF."""
        from src.functions.services.pdf_service import PdfSplitError

        with pytest.raises(PdfSplitError) as exc:
            pdf_service.get_page_count(b"not a valid pdf")

        assert "Failed to read PDF" in str(exc.value)

    def test_needs_splitting_true(self, pdf_service, six_page_pdf):
        """Test needs_splitting returns True for multi-page PDF."""
        assert pdf_service.needs_splitting(six_page_pdf) is True

    def test_needs_splitting_false(self, pdf_service, two_page_pdf):
        """Test needs_splitting returns False when pages <= pages_per_form."""
        assert pdf_service.needs_splitting(two_page_pdf) is False

    def test_needs_splitting_single_page(self, pdf_service, single_page_pdf):
        """Test needs_splitting returns False for single page."""
        assert pdf_service.needs_splitting(single_page_pdf) is False

    def test_split_pdf_no_split_needed(self, pdf_service, two_page_pdf):
        """Test split returns original when no splitting needed."""
        chunks = pdf_service.split_pdf(two_page_pdf)

        assert len(chunks) == 1
        pdf_bytes, start, end = chunks[0]
        assert start == 1
        assert end == 2
        # Verify page count of returned PDF
        assert pdf_service.get_page_count(pdf_bytes) == 2

    def test_split_pdf_even_pages(self, pdf_service, six_page_pdf):
        """Test splitting PDF with even number of pages."""
        chunks = pdf_service.split_pdf(six_page_pdf)

        assert len(chunks) == 3  # 6 pages / 2 pages per form = 3 chunks

        # Verify chunk 1: pages 1-2
        pdf1, start1, end1 = chunks[0]
        assert start1 == 1
        assert end1 == 2
        assert pdf_service.get_page_count(pdf1) == 2

        # Verify chunk 2: pages 3-4
        pdf2, start2, end2 = chunks[1]
        assert start2 == 3
        assert end2 == 4
        assert pdf_service.get_page_count(pdf2) == 2

        # Verify chunk 3: pages 5-6
        pdf3, start3, end3 = chunks[2]
        assert start3 == 5
        assert end3 == 6
        assert pdf_service.get_page_count(pdf3) == 2

    def test_split_pdf_odd_pages(self, pdf_service, five_page_pdf):
        """Test splitting PDF with odd number of pages."""
        chunks = pdf_service.split_pdf(five_page_pdf)

        assert len(chunks) == 3  # 5 pages / 2 pages per form = 3 chunks (last has 1 page)

        # Verify chunk 1: pages 1-2
        pdf1, start1, end1 = chunks[0]
        assert start1 == 1
        assert end1 == 2
        assert pdf_service.get_page_count(pdf1) == 2

        # Verify chunk 2: pages 3-4
        pdf2, start2, end2 = chunks[1]
        assert start2 == 3
        assert end2 == 4
        assert pdf_service.get_page_count(pdf2) == 2

        # Verify chunk 3: page 5 only
        pdf3, start3, end3 = chunks[2]
        assert start3 == 5
        assert end3 == 5
        assert pdf_service.get_page_count(pdf3) == 1

    def test_split_pdf_invalid(self, pdf_service):
        """Test error on invalid PDF."""
        from src.functions.services.pdf_service import PdfSplitError

        with pytest.raises(PdfSplitError) as exc:
            pdf_service.split_pdf(b"not a valid pdf")

        assert "Failed to split PDF" in str(exc.value)

    def test_extract_pages(self, pdf_service, six_page_pdf):
        """Test extracting specific page range."""
        extracted = pdf_service.extract_pages(six_page_pdf, 2, 4)

        # Should have pages 2, 3, 4 (3 pages)
        assert pdf_service.get_page_count(extracted) == 3

    def test_extract_pages_single(self, pdf_service, six_page_pdf):
        """Test extracting single page."""
        extracted = pdf_service.extract_pages(six_page_pdf, 3, 3)

        assert pdf_service.get_page_count(extracted) == 1

    def test_extract_pages_first_page(self, pdf_service, six_page_pdf):
        """Test extracting from first page."""
        extracted = pdf_service.extract_pages(six_page_pdf, 1, 2)

        assert pdf_service.get_page_count(extracted) == 2

    def test_extract_pages_last_pages(self, pdf_service, six_page_pdf):
        """Test extracting last pages."""
        extracted = pdf_service.extract_pages(six_page_pdf, 5, 6)

        assert pdf_service.get_page_count(extracted) == 2

    def test_extract_pages_all(self, pdf_service, six_page_pdf):
        """Test extracting all pages."""
        extracted = pdf_service.extract_pages(six_page_pdf, 1, 6)

        assert pdf_service.get_page_count(extracted) == 6

    def test_extract_pages_invalid_start_page(self, pdf_service, six_page_pdf):
        """Test error on invalid start page."""
        from src.functions.services.pdf_service import PdfSplitError

        with pytest.raises(PdfSplitError) as exc:
            pdf_service.extract_pages(six_page_pdf, 0, 2)

        assert "Invalid page range" in str(exc.value)

    def test_extract_pages_start_beyond_end(self, pdf_service, six_page_pdf):
        """Test error when start > end."""
        from src.functions.services.pdf_service import PdfSplitError

        with pytest.raises(PdfSplitError) as exc:
            pdf_service.extract_pages(six_page_pdf, 4, 2)

        assert "cannot be greater than" in str(exc.value)

    def test_extract_pages_end_beyond_total(self, pdf_service, six_page_pdf):
        """Test error when end page exceeds total."""
        from src.functions.services.pdf_service import PdfSplitError

        with pytest.raises(PdfSplitError) as exc:
            pdf_service.extract_pages(six_page_pdf, 5, 10)

        assert "Invalid page range" in str(exc.value)

    def test_extract_pages_invalid_pdf(self, pdf_service):
        """Test error on invalid PDF."""
        from src.functions.services.pdf_service import PdfSplitError

        with pytest.raises(PdfSplitError) as exc:
            pdf_service.extract_pages(b"not a valid pdf", 1, 2)

        assert "Failed to extract pages" in str(exc.value)


class TestFormBoundary:
    """Tests for FormBoundary dataclass."""

    def test_create_form_boundary(self):
        """Test creating a FormBoundary."""
        boundary = FormBoundary(
            start_page=1,
            end_page=2,
            confidence=0.9,
            detection_method="page_number",
        )
        assert boundary.start_page == 1
        assert boundary.end_page == 2
        assert boundary.confidence == 0.9
        assert boundary.detection_method == "page_number"

    def test_form_boundary_all_fields_required(self):
        """Test FormBoundary requires all fields."""
        boundary = FormBoundary(
            start_page=1, end_page=3, confidence=1.0, detection_method="fixed"
        )
        assert boundary.start_page == 1
        assert boundary.end_page == 3
        assert boundary.confidence == 1.0
        assert boundary.detection_method == "fixed"


class TestSmartFormDetection:
    """Tests for smart form boundary detection methods."""

    @pytest.fixture
    def pdf_service(self):
        """Create a PdfService instance."""
        return PdfService(pages_per_form=2)

    def test_get_page_header(self, pdf_service):
        """Test extracting page header."""
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        header = pdf_service._get_page_header(text, num_lines=3)
        assert header == "Line 1\nLine 2\nLine 3"

    def test_get_page_header_short_text(self, pdf_service):
        """Test header extraction with short text."""
        text = "Line 1\nLine 2"
        header = pdf_service._get_page_header(text, num_lines=5)
        assert header == "Line 1\nLine 2"

    def test_get_page_header_empty(self, pdf_service):
        """Test header extraction with empty text."""
        header = pdf_service._get_page_header("", num_lines=3)
        assert header == ""

    def test_get_page_footer(self, pdf_service):
        """Test extracting page footer."""
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        footer = pdf_service._get_page_footer(text, num_lines=2)
        assert footer == "Line 4\nLine 5"

    def test_get_page_footer_short_text(self, pdf_service):
        """Test footer extraction with short text."""
        text = "Line 1"
        footer = pdf_service._get_page_footer(text, num_lines=3)
        assert footer == "Line 1"

    def test_detect_page_number_pattern_page_of(self, pdf_service):
        """Test detecting 'Page X of Y' pattern."""
        text = "Some content\nPage 2 of 5\nMore content"
        result = pdf_service._detect_page_number_pattern(text)
        assert result == (2, 5)

    def test_detect_page_number_pattern_slash(self, pdf_service):
        """Test detecting 'X/Y' pattern."""
        text = "Invoice\n3/10"
        result = pdf_service._detect_page_number_pattern(text)
        assert result == (3, 10)

    def test_detect_page_number_pattern_pg(self, pdf_service):
        """Test detecting 'Pg X of Y' pattern."""
        text = "Document\nPg 1 of 3"
        result = pdf_service._detect_page_number_pattern(text)
        assert result == (1, 3)

    def test_detect_page_number_pattern_lowercase(self, pdf_service):
        """Test detecting lowercase 'page' pattern."""
        text = "page 4 of 8"
        result = pdf_service._detect_page_number_pattern(text)
        assert result == (4, 8)

    def test_detect_page_number_pattern_none(self, pdf_service):
        """Test no pattern found."""
        text = "Just some regular text without page numbers"
        result = pdf_service._detect_page_number_pattern(text)
        assert result is None

    def test_detect_page_number_pattern_invalid_range(self, pdf_service):
        """Test invalid page number range (current > total)."""
        text = "Page 5 of 3"  # Invalid: current > total
        result = pdf_service._detect_page_number_pattern(text)
        assert result is None

    def test_detect_page_number_pattern_too_many_pages(self, pdf_service):
        """Test page number beyond reasonable bounds."""
        text = "Page 1 of 100"  # Beyond max of 20
        result = pdf_service._detect_page_number_pattern(text)
        assert result is None

    def test_calculate_text_similarity_identical(self, pdf_service):
        """Test similarity of identical texts."""
        similarity = pdf_service._calculate_text_similarity("hello world", "hello world")
        assert similarity == 1.0

    def test_calculate_text_similarity_different(self, pdf_service):
        """Test similarity of completely different texts."""
        similarity = pdf_service._calculate_text_similarity("abc def", "xyz uvw")
        assert similarity == 0.0

    def test_calculate_text_similarity_partial(self, pdf_service):
        """Test similarity of partially matching texts."""
        similarity = pdf_service._calculate_text_similarity(
            "company invoice form", "company receipt form"
        )
        assert 0.0 < similarity < 1.0

    def test_calculate_text_similarity_empty(self, pdf_service):
        """Test similarity with empty text."""
        assert pdf_service._calculate_text_similarity("", "text") == 0.0
        assert pdf_service._calculate_text_similarity("text", "") == 0.0
        assert pdf_service._calculate_text_similarity("", "") == 0.0

    def test_calculate_text_similarity_case_insensitive(self, pdf_service):
        """Test similarity is case insensitive."""
        similarity = pdf_service._calculate_text_similarity("HELLO", "hello")
        assert similarity == 1.0

    def test_create_fixed_boundaries_even(self, pdf_service):
        """Test creating fixed boundaries with even pages."""
        boundaries = pdf_service._create_fixed_boundaries(total_pages=6, pages_per_form=2)

        assert len(boundaries) == 3
        assert boundaries[0].start_page == 1
        assert boundaries[0].end_page == 2
        assert boundaries[1].start_page == 3
        assert boundaries[1].end_page == 4
        assert boundaries[2].start_page == 5
        assert boundaries[2].end_page == 6

    def test_create_fixed_boundaries_odd(self, pdf_service):
        """Test creating fixed boundaries with odd pages."""
        boundaries = pdf_service._create_fixed_boundaries(total_pages=5, pages_per_form=2)

        assert len(boundaries) == 3
        assert boundaries[2].start_page == 5
        assert boundaries[2].end_page == 5  # Last form has only 1 page

    def test_create_fixed_boundaries_single(self, pdf_service):
        """Test creating fixed boundaries for single page."""
        boundaries = pdf_service._create_fixed_boundaries(total_pages=1, pages_per_form=2)

        assert len(boundaries) == 1
        assert boundaries[0].start_page == 1
        assert boundaries[0].end_page == 1
        assert boundaries[0].detection_method == "fixed"

    def test_detect_boundaries_from_page_numbers_no_patterns(self, pdf_service):
        """Test remaining pages boundary when no page number patterns found."""
        page_numbers = [None, None, None, None]
        boundaries = pdf_service._detect_boundaries_from_page_numbers(page_numbers, 4)
        # Method adds remaining pages as a catch-all boundary
        assert len(boundaries) == 1
        assert boundaries[0].start_page == 1
        assert boundaries[0].end_page == 4
        assert boundaries[0].confidence == 0.7

    def test_detect_boundaries_from_page_numbers_complete_forms(self, pdf_service):
        """Test boundary detection from page number patterns with complete forms."""
        # Single 2-page form with (1,2), (2,2) pattern
        page_numbers = [(1, 2), (2, 2)]
        boundaries = pdf_service._detect_boundaries_from_page_numbers(page_numbers, 2)

        # Should detect the completed form
        assert len(boundaries) >= 1
        assert boundaries[0].detection_method == "page_number"

    def test_detect_boundaries_from_page_numbers_new_form_start(self, pdf_service):
        """Test boundary when new form starts mid-document."""
        # First form 3 pages, second form starts on page 4
        page_numbers = [None, None, None, (1, 2), (2, 2)]
        boundaries = pdf_service._detect_boundaries_from_page_numbers(page_numbers, 5)

        # Should detect boundary when (1, X) appears after other pages
        assert len(boundaries) >= 1
        assert any(b.detection_method == "page_number" for b in boundaries)

    def test_detect_boundaries_from_headers_empty(self, pdf_service):
        """Test no boundaries with empty headers."""
        boundaries = pdf_service._detect_boundaries_from_headers([], 0.7, 0.5, 0)
        assert boundaries == []

    def test_detect_boundaries_from_headers_single(self, pdf_service):
        """Test no boundaries with single page."""
        boundaries = pdf_service._detect_boundaries_from_headers(
            ["Header"], 0.7, 0.5, 1
        )
        assert boundaries == []

    def test_detect_boundaries_from_headers_no_match(self, pdf_service):
        """Test no boundaries when headers don't match."""
        headers = ["Company A Form", "Different Content", "Another Thing", "Something Else"]
        boundaries = pdf_service._detect_boundaries_from_headers(headers, 0.7, 0.5, 4)
        assert boundaries == []

    def test_detect_boundaries_from_headers_matching(self, pdf_service):
        """Test boundary detection with matching headers."""
        headers = [
            "ACME Corp Invoice Form",
            "Details and items",
            "ACME Corp Invoice Form",  # Same header = new form
            "More details",
        ]
        boundaries = pdf_service._detect_boundaries_from_headers(headers, 0.7, 0.5, 4)

        # Should detect 2 forms
        assert len(boundaries) == 2
        assert boundaries[0].detection_method == "header_match"

    def test_detect_boundaries_from_headers_empty_first(self, pdf_service):
        """Test no boundaries when first header is empty."""
        headers = ["", "Content", "More Content"]
        boundaries = pdf_service._detect_boundaries_from_headers(headers, 0.7, 0.5, 3)
        assert boundaries == []


class TestDetectFormBoundaries:
    """Tests for detect_form_boundaries method."""

    @pytest.fixture
    def pdf_service(self):
        """Create a PdfService instance."""
        return PdfService(pages_per_form=2)

    def test_single_page_pdf(self, pdf_service):
        """Test single page returns single boundary."""
        pdf_content = create_test_pdf(1)
        boundaries = pdf_service.detect_form_boundaries(pdf_content)

        assert len(boundaries) == 1
        assert boundaries[0].start_page == 1
        assert boundaries[0].end_page == 1
        assert boundaries[0].detection_method == "single_page"

    def test_multi_page_pdf_returns_boundaries(self, pdf_service):
        """Test multi-page PDF returns form boundaries."""
        pdf_content = create_test_pdf(4)
        boundaries = pdf_service.detect_form_boundaries(pdf_content)

        # Should return at least one boundary
        assert len(boundaries) >= 1
        # All pages should be covered
        assert boundaries[0].start_page == 1
        assert boundaries[-1].end_page == 4

    def test_invalid_pdf_falls_back(self, pdf_service):
        """Test invalid PDF falls back to fixed boundaries."""
        # Mock to simulate exception
        with patch.object(pdf_service, "_extract_page_text", side_effect=Exception("Error")):
            pdf_content = create_test_pdf(4)
            boundaries = pdf_service.detect_form_boundaries(pdf_content)

            # Should still return boundaries despite error
            assert len(boundaries) >= 1


class TestSplitPdfSmart:
    """Tests for split_pdf_smart method."""

    @pytest.fixture
    def pdf_service(self):
        """Create a PdfService instance."""
        return PdfService(pages_per_form=2)

    def test_split_smart_fixed(self, pdf_service):
        """Test smart split with auto_detect=False uses fixed boundaries."""
        pdf_content = create_test_pdf(4)
        results = pdf_service.split_pdf_smart(pdf_content, auto_detect=False)

        assert len(results) == 2
        # Each result is (bytes, start, end, confidence)
        pdf_bytes, start, end, confidence = results[0]
        assert start == 1
        assert end == 2
        assert confidence == 1.0

    def test_split_smart_auto_detect(self, pdf_service):
        """Test smart split with auto_detect=True."""
        pdf_content = create_test_pdf(4)
        results = pdf_service.split_pdf_smart(pdf_content, auto_detect=True)

        # Should return boundaries with confidence
        assert len(results) >= 1
        for pdf_bytes, start, end, confidence in results:
            assert isinstance(pdf_bytes, bytes)
            assert start >= 1
            assert end >= start
            assert 0 <= confidence <= 1

    def test_split_smart_single_form_returns_original(self, pdf_service):
        """Test single form PDF returns original content."""
        pdf_content = create_test_pdf(2)
        results = pdf_service.split_pdf_smart(pdf_content, auto_detect=False)

        assert len(results) == 1
        pdf_bytes, start, end, confidence = results[0]
        # Original content should be returned (not re-extracted)
        assert start == 1
        assert end == 2


class TestExtractPageText:
    """Tests for _extract_page_text method."""

    @pytest.fixture
    def pdf_service(self):
        """Create a PdfService instance."""
        return PdfService(pages_per_form=2)

    def test_extract_text_from_blank_page(self, pdf_service):
        """Test extracting text from blank page returns empty string."""
        pdf_content = create_test_pdf(1)
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_content))
        text = pdf_service._extract_page_text(reader.pages[0])
        assert text == ""

    def test_extract_text_handles_exception(self, pdf_service):
        """Test text extraction handles exceptions gracefully."""
        mock_page = MagicMock()
        mock_page.extract_text.side_effect = Exception("Extraction error")

        text = pdf_service._extract_page_text(mock_page)
        assert text == ""

    def test_extract_text_handles_none_return(self, pdf_service):
        """Test text extraction handles None return."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = None

        text = pdf_service._extract_page_text(mock_page)
        assert text == ""
