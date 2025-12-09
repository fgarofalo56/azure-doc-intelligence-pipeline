"""Unit tests for the PDF service."""

import io

import pytest
from pypdf import PdfWriter


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
