"""PDF service for splitting multi-page PDFs.

Splits PDFs into chunks of specified page count for processing.
Supports both fixed page count and smart boundary detection.
"""

import io
import logging
import re
from dataclasses import dataclass

from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


@dataclass
class FormBoundary:
    """Represents a detected form boundary in a PDF."""

    start_page: int  # 1-indexed
    end_page: int  # 1-indexed
    confidence: float  # 0.0 to 1.0
    detection_method: str  # "header_match", "page_number", "content_similarity"


class PdfSplitError(Exception):
    """Raised when PDF splitting fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"PDF split failed: {reason}")


class PdfService:
    """Service for PDF manipulation operations."""

    def __init__(self, pages_per_form: int = 2) -> None:
        """Initialize PDF Service.

        Args:
            pages_per_form: Number of pages per form (default 2).
        """
        self.pages_per_form = pages_per_form

    def get_page_count(self, pdf_content: bytes) -> int:
        """Get the number of pages in a PDF.

        Args:
            pdf_content: PDF file content as bytes.

        Returns:
            int: Number of pages in the PDF.
        """
        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            return len(reader.pages)
        except Exception as e:
            logger.error(f"Failed to read PDF: {e}")
            raise PdfSplitError(f"Failed to read PDF: {e}") from e

    def needs_splitting(self, pdf_content: bytes) -> bool:
        """Check if PDF needs to be split.

        Args:
            pdf_content: PDF file content as bytes.

        Returns:
            bool: True if PDF has more pages than pages_per_form.
        """
        page_count = self.get_page_count(pdf_content)
        return page_count > self.pages_per_form

    def split_pdf(self, pdf_content: bytes) -> list[tuple[bytes, int, int]]:
        """Split PDF into chunks of pages_per_form pages each.

        Args:
            pdf_content: PDF file content as bytes.

        Returns:
            list: List of tuples (pdf_bytes, start_page, end_page).
                  start_page and end_page are 1-indexed.
        """
        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            total_pages = len(reader.pages)

            if total_pages <= self.pages_per_form:
                # No splitting needed, return original
                logger.info(f"PDF has {total_pages} pages, no splitting needed")
                return [(pdf_content, 1, total_pages)]

            chunks: list[tuple[bytes, int, int]] = []
            num_chunks = (total_pages + self.pages_per_form - 1) // self.pages_per_form

            logger.info(
                f"Splitting {total_pages}-page PDF into {num_chunks} chunks "
                f"of {self.pages_per_form} pages each"
            )

            for chunk_idx in range(num_chunks):
                start_page = chunk_idx * self.pages_per_form  # 0-indexed
                end_page = min(start_page + self.pages_per_form, total_pages)  # exclusive

                writer = PdfWriter()
                for page_idx in range(start_page, end_page):
                    writer.add_page(reader.pages[page_idx])

                # Write to bytes
                output = io.BytesIO()
                writer.write(output)
                output.seek(0)
                chunk_bytes = output.read()

                # Convert to 1-indexed for logging/naming
                chunks.append((chunk_bytes, start_page + 1, end_page))

                logger.info(f"Created chunk {chunk_idx + 1}: pages {start_page + 1}-{end_page}")

            return chunks

        except Exception as e:
            logger.error(f"Failed to split PDF: {e}")
            raise PdfSplitError(f"Failed to split PDF: {e}") from e

    def extract_pages(
        self,
        pdf_content: bytes,
        start_page: int,
        end_page: int,
    ) -> bytes:
        """Extract a specific range of pages from a PDF.

        Args:
            pdf_content: PDF file content as bytes.
            start_page: First page to extract (1-indexed).
            end_page: Last page to extract (1-indexed, inclusive).

        Returns:
            bytes: PDF content containing only the specified pages.

        Raises:
            PdfSplitError: If extraction fails or page range is invalid.
        """
        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            total_pages = len(reader.pages)

            # Validate page range
            if start_page < 1 or end_page > total_pages:
                raise PdfSplitError(
                    f"Invalid page range {start_page}-{end_page}. PDF has {total_pages} pages."
                )

            if start_page > end_page:
                raise PdfSplitError(
                    f"Start page ({start_page}) cannot be greater than end page ({end_page})"
                )

            writer = PdfWriter()

            # Pages are 0-indexed in pypdf
            for page_idx in range(start_page - 1, end_page):
                writer.add_page(reader.pages[page_idx])

            # Write to bytes
            output = io.BytesIO()
            writer.write(output)
            output.seek(0)

            logger.info(f"Extracted pages {start_page}-{end_page} from {total_pages}-page PDF")
            return output.read()

        except PdfSplitError:
            raise
        except Exception as e:
            logger.error(f"Failed to extract pages: {e}")
            raise PdfSplitError(f"Failed to extract pages: {e}") from e

    def _extract_page_text(self, page) -> str:
        """Extract text from a PDF page.

        Args:
            page: A pypdf page object.

        Returns:
            str: Extracted text content.
        """
        try:
            return page.extract_text() or ""
        except Exception:
            return ""

    def _get_page_header(self, text: str, num_lines: int = 3) -> str:
        """Get the first N lines of page text as header.

        Args:
            text: Full page text.
            num_lines: Number of lines to consider as header.

        Returns:
            str: Header text (first N lines).
        """
        lines = text.strip().split("\n")[:num_lines]
        return "\n".join(lines).strip()

    def _get_page_footer(self, text: str, num_lines: int = 2) -> str:
        """Get the last N lines of page text as footer.

        Args:
            text: Full page text.
            num_lines: Number of lines to consider as footer.

        Returns:
            str: Footer text (last N lines).
        """
        lines = text.strip().split("\n")[-num_lines:]
        return "\n".join(lines).strip()

    def _detect_page_number_pattern(self, text: str) -> tuple[int, int] | None:
        """Detect page numbering pattern like 'Page X of Y' or 'X/Y'.

        Args:
            text: Page text content.

        Returns:
            tuple: (current_page, total_pages) if found, None otherwise.
        """
        # Common page number patterns
        patterns = [
            r"[Pp]age\s+(\d+)\s+of\s+(\d+)",  # "Page 1 of 3"
            r"(\d+)\s*/\s*(\d+)",  # "1/3" or "1 / 3"
            r"[Pp]g\.?\s*(\d+)\s+of\s+(\d+)",  # "Pg 1 of 3"
            r"-\s*(\d+)\s*-\s*.*?(\d+)\s*pages?",  # "- 1 - of 3 pages"
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    if 1 <= current <= total <= 20:  # Reasonable bounds
                        return (current, total)
                except (ValueError, IndexError):
                    continue
        return None

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity between two strings.

        Uses Jaccard similarity on word sets.

        Args:
            text1: First text.
            text2: Second text.

        Returns:
            float: Similarity score from 0.0 to 1.0.
        """
        if not text1 or not text2:
            return 0.0

        # Normalize and tokenize
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def detect_form_boundaries(
        self,
        pdf_content: bytes,
        header_similarity_threshold: float = 0.7,
        min_confidence: float = 0.5,
    ) -> list[FormBoundary]:
        """Detect form boundaries in a PDF using content analysis.

        Uses multiple detection strategies:
        1. Page numbering patterns (e.g., "Page 1 of 2")
        2. Header similarity (forms often have similar first lines)
        3. Content structure changes

        Args:
            pdf_content: PDF file content as bytes.
            header_similarity_threshold: Minimum similarity for headers to be
                considered matching (0.0-1.0).
            min_confidence: Minimum confidence to accept a boundary (0.0-1.0).

        Returns:
            list[FormBoundary]: Detected form boundaries.
        """
        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            total_pages = len(reader.pages)

            if total_pages <= 1:
                return [FormBoundary(1, 1, 1.0, "single_page")]

            # Extract text from all pages
            page_texts: list[str] = []
            page_headers: list[str] = []
            page_footers: list[str] = []
            page_numbers: list[tuple[int, int] | None] = []

            for page in reader.pages:
                text = self._extract_page_text(page)
                page_texts.append(text)
                page_headers.append(self._get_page_header(text))
                page_footers.append(self._get_page_footer(text))
                page_numbers.append(self._detect_page_number_pattern(text))

            # Strategy 1: Detect boundaries from page numbers
            boundaries = self._detect_boundaries_from_page_numbers(
                page_numbers, total_pages
            )
            if boundaries:
                logger.info(f"Detected {len(boundaries)} forms via page numbers")
                return boundaries

            # Strategy 2: Detect boundaries from header similarity
            boundaries = self._detect_boundaries_from_headers(
                page_headers, header_similarity_threshold, min_confidence, total_pages
            )
            if boundaries:
                logger.info(f"Detected {len(boundaries)} forms via header matching")
                return boundaries

            # Strategy 3: Fall back to fixed pages_per_form
            logger.info("No clear boundaries detected, using fixed page count")
            return self._create_fixed_boundaries(total_pages, self.pages_per_form)

        except Exception as e:
            logger.warning(f"Form boundary detection failed: {e}, using fixed split")
            reader = PdfReader(io.BytesIO(pdf_content))
            return self._create_fixed_boundaries(
                len(reader.pages), self.pages_per_form
            )

    def _detect_boundaries_from_page_numbers(
        self,
        page_numbers: list[tuple[int, int] | None],
        total_pages: int,
    ) -> list[FormBoundary]:
        """Detect boundaries using page numbering patterns.

        Args:
            page_numbers: List of (current, total) tuples for each page.
            total_pages: Total pages in PDF.

        Returns:
            list[FormBoundary]: Detected boundaries.
        """
        boundaries: list[FormBoundary] = []
        current_form_start = 1

        for page_idx, page_num in enumerate(page_numbers):
            page_1_indexed = page_idx + 1

            if page_num:
                current_page, total_in_form = page_num

                # If this is "Page 1 of N" and not the first page overall
                if current_page == 1 and page_idx > 0:
                    # Previous pages form a boundary
                    boundaries.append(
                        FormBoundary(
                            start_page=current_form_start,
                            end_page=page_1_indexed - 1,
                            confidence=0.9,
                            detection_method="page_number",
                        )
                    )
                    current_form_start = page_1_indexed

                # If this is the last page of a form
                if current_page == total_in_form:
                    boundaries.append(
                        FormBoundary(
                            start_page=current_form_start,
                            end_page=page_1_indexed,
                            confidence=0.95,
                            detection_method="page_number",
                        )
                    )
                    current_form_start = page_1_indexed + 1

        # Handle remaining pages if any
        if current_form_start <= total_pages and (
            not boundaries or boundaries[-1].end_page < total_pages
        ):
            boundaries.append(
                FormBoundary(
                    start_page=current_form_start,
                    end_page=total_pages,
                    confidence=0.7,
                    detection_method="page_number",
                )
            )

        return boundaries if boundaries else []

    def _detect_boundaries_from_headers(
        self,
        page_headers: list[str],
        similarity_threshold: float,
        min_confidence: float,
        total_pages: int,
    ) -> list[FormBoundary]:
        """Detect boundaries using header similarity.

        Forms often start with similar headers (company name, form title, etc.)

        Args:
            page_headers: List of header text for each page.
            similarity_threshold: Minimum similarity to consider headers matching.
            min_confidence: Minimum confidence for boundary detection.
            total_pages: Total pages in PDF.

        Returns:
            list[FormBoundary]: Detected boundaries.
        """
        if not page_headers or len(page_headers) < 2:
            return []

        # Find pages with similar headers to the first page
        first_header = page_headers[0]
        if not first_header.strip():
            return []

        form_start_pages: list[int] = [0]  # First page always starts a form

        for page_idx in range(1, len(page_headers)):
            similarity = self._calculate_text_similarity(
                first_header, page_headers[page_idx]
            )
            if similarity >= similarity_threshold:
                form_start_pages.append(page_idx)

        # Need at least 2 form starts to create boundaries
        if len(form_start_pages) < 2:
            return []

        # Calculate average form length for confidence
        avg_form_length = total_pages / len(form_start_pages)
        boundaries: list[FormBoundary] = []

        for i, start_idx in enumerate(form_start_pages):
            if i < len(form_start_pages) - 1:
                end_idx = form_start_pages[i + 1] - 1
            else:
                end_idx = total_pages - 1

            # Calculate confidence based on how consistent form lengths are
            form_length = end_idx - start_idx + 1
            length_diff = abs(form_length - avg_form_length)
            confidence = max(min_confidence, 1.0 - (length_diff / avg_form_length))

            boundaries.append(
                FormBoundary(
                    start_page=start_idx + 1,
                    end_page=end_idx + 1,
                    confidence=confidence,
                    detection_method="header_match",
                )
            )

        return boundaries

    def _create_fixed_boundaries(
        self, total_pages: int, pages_per_form: int
    ) -> list[FormBoundary]:
        """Create fixed-size form boundaries.

        Args:
            total_pages: Total pages in PDF.
            pages_per_form: Pages per form.

        Returns:
            list[FormBoundary]: Fixed boundaries.
        """
        boundaries: list[FormBoundary] = []
        num_forms = (total_pages + pages_per_form - 1) // pages_per_form

        for i in range(num_forms):
            start_page = i * pages_per_form + 1
            end_page = min((i + 1) * pages_per_form, total_pages)
            boundaries.append(
                FormBoundary(
                    start_page=start_page,
                    end_page=end_page,
                    confidence=1.0,
                    detection_method="fixed",
                )
            )

        return boundaries

    def split_pdf_smart(
        self,
        pdf_content: bytes,
        auto_detect: bool = False,
        header_similarity_threshold: float = 0.7,
    ) -> list[tuple[bytes, int, int, float]]:
        """Split PDF using smart boundary detection or fixed pages.

        Args:
            pdf_content: PDF file content as bytes.
            auto_detect: If True, attempt automatic boundary detection.
                         If False, use fixed pages_per_form.
            header_similarity_threshold: Threshold for header matching.

        Returns:
            list: List of tuples (pdf_bytes, start_page, end_page, confidence).
        """
        if auto_detect:
            boundaries = self.detect_form_boundaries(
                pdf_content,
                header_similarity_threshold=header_similarity_threshold,
            )
        else:
            reader = PdfReader(io.BytesIO(pdf_content))
            total_pages = len(reader.pages)
            boundaries = self._create_fixed_boundaries(total_pages, self.pages_per_form)

        results: list[tuple[bytes, int, int, float]] = []

        for boundary in boundaries:
            if boundary.start_page == 1 and boundary.end_page == len(
                PdfReader(io.BytesIO(pdf_content)).pages
            ):
                # Single form, return original
                results.append(
                    (
                        pdf_content,
                        boundary.start_page,
                        boundary.end_page,
                        boundary.confidence,
                    )
                )
            else:
                chunk_bytes = self.extract_pages(
                    pdf_content, boundary.start_page, boundary.end_page
                )
                results.append(
                    (
                        chunk_bytes,
                        boundary.start_page,
                        boundary.end_page,
                        boundary.confidence,
                    )
                )

            logger.info(
                f"Form boundary: pages {boundary.start_page}-{boundary.end_page} "
                f"(confidence: {boundary.confidence:.2f}, method: {boundary.detection_method})"
            )

        return results
