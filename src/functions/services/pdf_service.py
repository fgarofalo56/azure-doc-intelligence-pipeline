"""PDF service for splitting multi-page PDFs.

Splits PDFs into chunks of specified page count for processing.
"""

import io
import logging
from typing import BinaryIO

from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


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

                logger.info(
                    f"Created chunk {chunk_idx + 1}: pages {start_page + 1}-{end_page}"
                )

            return chunks

        except Exception as e:
            logger.error(f"Failed to split PDF: {e}")
            raise PdfSplitError(f"Failed to split PDF: {e}") from e
