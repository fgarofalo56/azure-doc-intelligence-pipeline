"""Document Intelligence service for PDF processing.

Implements async document analysis with retry logic and rate limiting.
"""

import asyncio
import logging
from typing import Any

from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

logger = logging.getLogger(__name__)


class DocumentProcessingError(Exception):
    """Raised when document processing fails."""

    def __init__(self, blob_name: str, reason: str) -> None:
        self.blob_name = blob_name
        self.reason = reason
        super().__init__(f"Failed to process {blob_name}: {reason}")


class RateLimitError(Exception):
    """Raised when rate limit is exceeded after retries."""

    pass


class DocumentService:
    """Async Document Intelligence service with retry and rate limiting."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        max_concurrent: int = 10,
        max_retries: int = 5,
        initial_retry_delay: float = 2.0,
    ) -> None:
        """Initialize Document Service.

        Args:
            endpoint: Document Intelligence endpoint URL.
            api_key: API key for authentication.
            max_concurrent: Maximum concurrent requests (default 10, stay below 15 TPS).
            max_retries: Maximum retry attempts for rate limits.
            initial_retry_delay: Initial delay before retry in seconds.
        """
        self.endpoint = endpoint
        self.credential = AzureKeyCredential(api_key)
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        # CRITICAL: Use semaphore for concurrency control to stay below 15 TPS
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_document(
        self,
        blob_url: str,
        model_id: str,
        blob_name: str = "",
    ) -> dict[str, Any]:
        """Analyze a document using Document Intelligence.

        CRITICAL: Implements exponential backoff retry from begin_analyze_document,
        not from poller.result() - once SDK exhausts retries, poller won't retry.

        Args:
            blob_url: SAS URL to the blob document.
            model_id: Document Intelligence model ID.
            blob_name: Original blob name for error reporting.

        Returns:
            dict: Extracted document data with fields, confidence scores, etc.

        Raises:
            DocumentProcessingError: If processing fails after retries.
            RateLimitError: If rate limit exceeded after all retries.
        """
        async with self.semaphore:  # CRITICAL: Concurrency control
            for attempt in range(self.max_retries):
                try:
                    async with DocumentIntelligenceClient(
                        endpoint=self.endpoint,
                        credential=self.credential,
                    ) as client:
                        logger.info(
                            f"Analyzing document (attempt {attempt + 1}/{self.max_retries}): {blob_name or blob_url[:50]}"
                        )

                        # Analyze ALL pages (1- means page 1 to end)
                        poller = await client.begin_analyze_document(
                            model_id=model_id,
                            body=AnalyzeDocumentRequest(url_source=blob_url),
                            pages="1-",  # Analyze all pages
                        )

                        result = await poller.result()

                        # Log diagnostic info
                        num_pages = len(result.pages) if result.pages else 0
                        num_docs = len(result.documents) if result.documents else 0
                        logger.info(
                            f"Document Intelligence returned: {num_pages} pages, {num_docs} documents"
                        )

                        return self._extract_result(result, model_id)

                except HttpResponseError as e:
                    if e.status_code == 429:
                        if attempt < self.max_retries - 1:
                            # CRITICAL: Exponential backoff - must restart entire operation
                            delay = self.initial_retry_delay * (2**attempt)
                            logger.warning(
                                f"Rate limited (429). Retrying in {delay:.1f}s "
                                f"(attempt {attempt + 1}/{self.max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                        raise RateLimitError(
                            f"Rate limit exceeded after {self.max_retries} retries"
                        ) from e
                    else:
                        logger.error(f"HTTP error {e.status_code}: {e.message}")
                        raise DocumentProcessingError(
                            blob_name or blob_url, f"HTTP {e.status_code}: {e.message}"
                        ) from e

                except Exception as e:
                    logger.exception(f"Unexpected error processing document: {e}")
                    raise DocumentProcessingError(
                        blob_name or blob_url, str(e)
                    ) from e

            raise DocumentProcessingError(
                blob_name or blob_url,
                f"Failed after {self.max_retries} attempts",
            )

    def _extract_result(self, result: Any, model_id: str) -> dict[str, Any]:
        """Extract fields and confidence from analysis result.

        Processes ALL documents/pages in the result, not just the first one.
        Also captures page-level data from result.pages for comprehensive extraction.

        Args:
            result: AnalyzeResult from Document Intelligence.
            model_id: Model ID used for analysis.

        Returns:
            dict: Extracted data with fields, confidence, etc.
                  For multi-page documents, includes 'pages' array.
        """
        # Get actual page count from result.pages (not result.documents)
        actual_page_count = len(result.pages) if result.pages else 0
        num_documents = len(result.documents) if result.documents else 0

        extracted_data: dict[str, Any] = {
            "modelId": model_id,
            "docType": None,
            "modelConfidence": None,
            "fields": {},
            "confidence": {},
            "status": "completed",
            "error": None,
            "pageCount": actual_page_count,
            "documentCount": num_documents,
        }

        logger.info(
            f"Extracting from {actual_page_count} pages, {num_documents} recognized documents"
        )

        # Process recognized documents (forms that match the model)
        if result.documents:
            if num_documents == 1:
                # Single document - check which pages it spans
                document = result.documents[0]
                extracted_data["docType"] = document.doc_type
                extracted_data["modelConfidence"] = document.confidence

                # Get the bounding regions to see which pages this document spans
                doc_pages = set()
                if hasattr(document, "bounding_regions") and document.bounding_regions:
                    for region in document.bounding_regions:
                        doc_pages.add(region.page_number)

                if doc_pages:
                    logger.info(f"Document spans pages: {sorted(doc_pages)}")
                    extracted_data["documentPages"] = sorted(doc_pages)

                if document.fields:
                    for field_name, field_value in document.fields.items():
                        value = self._extract_field_value(field_value)
                        confidence = getattr(field_value, "confidence", None)

                        # Check which page this field is on
                        field_page = None
                        if hasattr(field_value, "bounding_regions") and field_value.bounding_regions:
                            field_page = field_value.bounding_regions[0].page_number

                        # Store with page prefix if multi-page document
                        if field_page and actual_page_count > 1:
                            prefixed_name = f"page{field_page}_{field_name}"
                            extracted_data["fields"][prefixed_name] = value
                            if confidence is not None:
                                extracted_data["confidence"][prefixed_name] = confidence

                        # Also store without prefix for single-page compatibility
                        extracted_data["fields"][field_name] = value
                        if confidence is not None:
                            extracted_data["confidence"][field_name] = confidence
            else:
                # Multiple documents - process each
                pages: list[dict[str, Any]] = []
                all_confidences: list[float] = []

                for doc_idx, document in enumerate(result.documents, start=1):
                    # Get the actual page number from bounding regions
                    doc_page_num = doc_idx
                    if hasattr(document, "bounding_regions") and document.bounding_regions:
                        doc_page_num = document.bounding_regions[0].page_number

                    page_data: dict[str, Any] = {
                        "pageNumber": doc_page_num,
                        "documentIndex": doc_idx,
                        "docType": document.doc_type,
                        "confidence": document.confidence,
                        "fields": {},
                        "fieldConfidence": {},
                    }

                    if document.confidence is not None:
                        all_confidences.append(document.confidence)

                    if document.fields:
                        for field_name, field_value in document.fields.items():
                            value = self._extract_field_value(field_value)
                            confidence = getattr(field_value, "confidence", None)

                            page_data["fields"][field_name] = value
                            if confidence is not None:
                                page_data["fieldConfidence"][field_name] = confidence

                    pages.append(page_data)
                    logger.info(
                        f"Extracted {len(page_data['fields'])} fields from document {doc_idx} (page {doc_page_num})"
                    )

                extracted_data["pages"] = pages
                extracted_data["docType"] = result.documents[0].doc_type
                if all_confidences:
                    extracted_data["modelConfidence"] = sum(all_confidences) / len(
                        all_confidences
                    )

                # Populate top-level fields with page prefix
                for page in pages:
                    page_prefix = f"page{page['pageNumber']}_"
                    for field_name, field_value in page["fields"].items():
                        extracted_data["fields"][page_prefix + field_name] = field_value
                    for field_name, conf in page["fieldConfidence"].items():
                        extracted_data["confidence"][page_prefix + field_name] = conf
        else:
            logger.warning(
                f"No documents recognized by model '{model_id}'. "
                f"The model may not match the document layout on pages 2+. "
                f"Consider using 'prebuilt-layout' for generic extraction."
            )

        # Log warning if pages were analyzed but not all recognized
        if actual_page_count > num_documents:
            logger.warning(
                f"Only {num_documents} of {actual_page_count} pages were recognized as matching the model. "
                f"Pages without matching forms won't have extracted fields."
            )
            extracted_data["_warning"] = (
                f"Only {num_documents} of {actual_page_count} pages matched the model"
            )

        return extracted_data

    def _extract_field_value(self, field: Any) -> Any:
        """Extract value from field based on type.

        CRITICAL: Field structure varies by model - always use .get() with fallbacks.

        Args:
            field: Field object from Document Intelligence.

        Returns:
            Extracted value (string, number, date, etc.).
        """
        if field is None:
            return None

        # Try to get typed value based on field type
        # String fields
        if hasattr(field, "value_string") and field.value_string is not None:
            return field.value_string

        # Number fields
        if hasattr(field, "value_number") and field.value_number is not None:
            return field.value_number

        # Date fields
        if hasattr(field, "value_date") and field.value_date is not None:
            return str(field.value_date)

        # Currency fields
        if hasattr(field, "value_currency") and field.value_currency is not None:
            currency = field.value_currency
            return {
                "amount": getattr(currency, "amount", None),
                "currencyCode": getattr(currency, "currency_code", "USD"),
            }

        # Array fields
        if hasattr(field, "value_array") and field.value_array is not None:
            return [self._extract_field_value(item) for item in field.value_array]

        # Object fields
        if hasattr(field, "value_object") and field.value_object is not None:
            return {
                key: self._extract_field_value(val)
                for key, val in field.value_object.items()
            }

        # Fallback to content
        if hasattr(field, "content"):
            return field.content

        return None
