"""Azure Functions main entry point.

HTTP triggers for document processing with Document Intelligence.
Supports automatic splitting of multi-page PDFs into 2-page form chunks.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import azure.functions as func

from config import ConfigurationError, get_config
from services import get_blob_service, get_cosmos_service, get_document_service, get_pdf_service
from services.blob_service import BlobServiceError
from services.cosmos_service import CosmosError
from services.document_service import DocumentProcessingError, RateLimitError
from services.pdf_service import PdfSplitError

# Number of pages per form (forms are 2 pages each)
PAGES_PER_FORM = 2

# Initialize function app
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

logger = logging.getLogger(__name__)


def create_response(
    data: dict[str, Any],
    status_code: int = 200,
) -> func.HttpResponse:
    """Create JSON HTTP response.

    Args:
        data: Response data dictionary.
        status_code: HTTP status code.

    Returns:
        func.HttpResponse: JSON response.
    """
    return func.HttpResponse(
        body=json.dumps(data),
        status_code=status_code,
        mimetype="application/json",
    )


def create_error_response(
    error: str,
    status_code: int = 500,
    details: dict[str, Any] | None = None,
) -> func.HttpResponse:
    """Create error JSON response.

    Args:
        error: Error message.
        status_code: HTTP status code.
        details: Additional error details.

    Returns:
        func.HttpResponse: Error JSON response.
    """
    body: dict[str, Any] = {
        "status": "error",
        "error": error,
    }
    if details:
        body["details"] = details

    return func.HttpResponse(
        body=json.dumps(body),
        status_code=status_code,
        mimetype="application/json",
    )


@app.function_name(name="ProcessDocument")
@app.route(route="process", methods=["POST"])
async def process_document(req: func.HttpRequest) -> func.HttpResponse:
    """Process a PDF document through Document Intelligence.

    Automatically splits multi-page PDFs into 2-page form chunks.

    Request body:
        {
            "blobUrl": "https://storage.blob.core.windows.net/container/file.pdf?sas=...",
            "blobName": "folder/file.pdf",
            "modelId": "custom-model-v1"  // optional, defaults to prebuilt-layout
        }

    Response:
        {
            "status": "success",
            "documentId": "folder_file_pdf",
            "processedAt": "2024-01-15T10:30:00Z",
            "formsProcessed": 3  // number of 2-page forms processed
        }
    """
    logger.info("ProcessDocument HTTP trigger invoked")

    # Parse request body
    try:
        req_body = req.get_json()
    except ValueError:
        return create_error_response(
            "Invalid JSON in request body",
            status_code=400,
        )

    # Validate required fields
    blob_url = req_body.get("blobUrl")
    blob_name = req_body.get("blobName")

    if not blob_url:
        return create_error_response(
            "Missing required field: blobUrl",
            status_code=400,
        )
    if not blob_name:
        return create_error_response(
            "Missing required field: blobName",
            status_code=400,
        )

    # Get model ID (optional, defaults to configured default)
    try:
        config = get_config()
        model_id = req_body.get("modelId", config.default_model_id)
    except ConfigurationError as e:
        return create_error_response(
            f"Configuration error: {e}",
            status_code=500,
        )

    try:
        blob_service = get_blob_service()
        if not blob_service:
            return create_error_response(
                "Storage connection not configured",
                status_code=500,
            )

        # Download the PDF to check if splitting is needed
        logger.info(f"Downloading PDF: {blob_name}")
        pdf_content = blob_service.download_blob(blob_url)

        # Check if PDF needs splitting
        pdf_service = get_pdf_service(pages_per_form=PAGES_PER_FORM)
        page_count = pdf_service.get_page_count(pdf_content)
        logger.info(f"PDF has {page_count} pages")

        # Parse original blob info
        container_name, original_blob_path = blob_service.parse_blob_url(blob_url)
        base_name = original_blob_path.rsplit(".", 1)[0]  # Remove .pdf extension

        processed_at = datetime.now(timezone.utc).isoformat()
        doc_service = get_document_service()
        cosmos_service = get_cosmos_service()

        if page_count <= PAGES_PER_FORM:
            # No splitting needed - process as single document
            logger.info("No splitting needed, processing as single form")

            url_with_sas = blob_service.generate_sas_url(blob_url)
            analysis_result = await doc_service.analyze_document(
                blob_url=url_with_sas,
                model_id=model_id,
                blob_name=blob_name,
            )

            doc_id = blob_name.replace("/", "_").replace(".", "_")
            document = {
                "id": doc_id,
                "sourceFile": blob_name,
                "processedAt": processed_at,
                "formNumber": 1,
                "totalForms": 1,
                **analysis_result,
            }

            await cosmos_service.save_document_result(document)

            return create_response(
                {
                    "status": "success",
                    "documentId": doc_id,
                    "processedAt": processed_at,
                    "formsProcessed": 1,
                },
                status_code=200,
            )

        # Split PDF into 2-page chunks
        logger.info(f"Splitting {page_count}-page PDF into {PAGES_PER_FORM}-page forms")
        chunks = pdf_service.split_pdf(pdf_content)
        total_forms = len(chunks)

        logger.info(f"Split into {total_forms} forms")

        # Process each chunk
        results: list[dict[str, Any]] = []
        temp_blobs: list[str] = []  # Track temp blobs for cleanup

        for form_num, (chunk_bytes, start_page, end_page) in enumerate(chunks, start=1):
            # Upload chunk to temp location
            chunk_blob_name = f"{base_name}_form{form_num}_pages{start_page}-{end_page}.pdf"
            temp_blob_path = f"_temp/{chunk_blob_name}"

            logger.info(f"Processing form {form_num}/{total_forms}: pages {start_page}-{end_page}")

            try:
                # Upload temp blob
                chunk_url = blob_service.upload_blob(
                    container_name=container_name,
                    blob_name=temp_blob_path,
                    content=chunk_bytes,
                )
                temp_blobs.append(temp_blob_path)

                # Generate SAS and process
                chunk_sas_url = blob_service.generate_sas_url(chunk_url)
                analysis_result = await doc_service.analyze_document(
                    blob_url=chunk_sas_url,
                    model_id=model_id,
                    blob_name=f"{blob_name} (form {form_num}, pages {start_page}-{end_page})",
                )

                # Create document ID for this form
                doc_id = f"{blob_name.replace('/', '_').replace('.', '_')}_form{form_num}"

                document = {
                    "id": doc_id,
                    "sourceFile": blob_name,  # Partition key - same for all forms from this PDF
                    "processedAt": processed_at,
                    "formNumber": form_num,
                    "totalForms": total_forms,
                    "pageRange": f"{start_page}-{end_page}",
                    "originalPageCount": page_count,
                    **analysis_result,
                }

                await cosmos_service.save_document_result(document)

                results.append({
                    "formNumber": form_num,
                    "documentId": doc_id,
                    "pageRange": f"{start_page}-{end_page}",
                    "status": "success",
                })

                logger.info(f"Successfully processed form {form_num}")

            except (DocumentProcessingError, RateLimitError) as e:
                logger.error(f"Failed to process form {form_num}: {e}")
                results.append({
                    "formNumber": form_num,
                    "pageRange": f"{start_page}-{end_page}",
                    "status": "failed",
                    "error": str(e),
                })

        # Cleanup temp blobs
        for temp_blob in temp_blobs:
            try:
                blob_service.delete_blob(container_name, temp_blob)
            except Exception as e:
                logger.warning(f"Failed to delete temp blob {temp_blob}: {e}")

        # Count successes
        successful = sum(1 for r in results if r["status"] == "success")

        return create_response(
            {
                "status": "success" if successful == total_forms else "partial",
                "processedAt": processed_at,
                "formsProcessed": successful,
                "totalForms": total_forms,
                "originalPageCount": page_count,
                "results": results,
            },
            status_code=200,
        )

    except PdfSplitError as e:
        logger.error(f"PDF split error: {e}")
        return create_error_response(
            f"Failed to split PDF: {e.reason}",
            status_code=500,
            details={"blobName": blob_name},
        )

    except BlobServiceError as e:
        logger.error(f"Blob service error: {e}")
        return create_error_response(
            f"Failed to access blob: {e.reason}",
            status_code=500,
            details={"blobName": blob_name},
        )

    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded: {e}")
        return create_error_response(
            "Document Intelligence rate limit exceeded. Please retry later.",
            status_code=429,
            details={"blobName": blob_name},
        )

    except DocumentProcessingError as e:
        logger.error(f"Document processing error: {e}")
        # Save error state to Cosmos DB
        try:
            cosmos_service = get_cosmos_service()
            doc_id = blob_name.replace("/", "_").replace(".", "_")
            error_document = {
                "id": doc_id,
                "sourceFile": blob_name,
                "processedAt": datetime.now(timezone.utc).isoformat(),
                "status": "failed",
                "error": str(e),
                "fields": {},
                "confidence": {},
            }
            await cosmos_service.save_document_result(error_document)
        except Exception:
            logger.exception("Failed to save error document")

        return create_error_response(
            f"Document processing failed: {e.reason}",
            status_code=500,
            details={"blobName": blob_name},
        )

    except CosmosError as e:
        logger.error(f"Cosmos DB error: {e}")
        return create_error_response(
            f"Database error: {e.reason}",
            status_code=500,
            details={"operation": e.operation},
        )

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return create_error_response(
            "Internal server error",
            status_code=500,
        )


@app.function_name(name="GetDocumentStatus")
@app.route(route="status/{blob_name}", methods=["GET"])
async def get_document_status(req: func.HttpRequest) -> func.HttpResponse:
    """Get processing status for a document.

    Path parameters:
        blob_name: URL-encoded blob path

    Response:
        {
            "status": "completed" | "failed" | "not_found",
            "documentId": "folder_file_pdf",
            "sourceFile": "folder/file.pdf"
        }
    """
    logger.info("GetDocumentStatus HTTP trigger invoked")

    blob_name = req.route_params.get("blob_name")
    if not blob_name:
        return create_error_response(
            "Missing blob_name in path",
            status_code=400,
        )

    try:
        cosmos_service = get_cosmos_service()
        doc_id = blob_name.replace("/", "_").replace(".", "_")

        doc = await cosmos_service.get_document(doc_id, blob_name)

        if doc:
            return create_response(
                {
                    "status": doc.get("status", "unknown"),
                    "documentId": doc_id,
                    "sourceFile": blob_name,
                    "processedAt": doc.get("processedAt"),
                }
            )
        else:
            return create_response(
                {
                    "status": "not_found",
                    "documentId": doc_id,
                    "sourceFile": blob_name,
                },
                status_code=404,
            )

    except CosmosError as e:
        logger.error(f"Cosmos DB error: {e}")
        return create_error_response(
            f"Database error: {e.reason}",
            status_code=500,
        )

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return create_error_response(
            "Internal server error",
            status_code=500,
        )


@app.function_name(name="Health")
@app.route(route="health", methods=["GET"])
async def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint.

    Response:
        {
            "status": "healthy",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    return create_response(
        {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
