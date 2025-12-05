"""Azure Functions main entry point.

HTTP triggers for document processing with Document Intelligence.
Supports automatic splitting of multi-page PDFs into 2-page form chunks.

Endpoints:
- POST /api/process - Process a PDF document
- POST /api/reprocess/{blob_name} - Reprocess a failed document
- GET /api/status/{blob_name} - Get processing status for a document
- GET /api/status/batch/{blob_name} - Get all forms from a multi-page PDF
- DELETE /api/documents/{blob_name} - Delete processed documents and split PDFs
- GET /api/health - Health check endpoint
- Blob trigger - Auto-process PDFs uploaded to incoming/
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

import azure.functions as func

from config import ConfigurationError, get_config
from services import (
    get_blob_service,
    get_cosmos_service,
    get_document_service,
    get_pdf_service,
    get_telemetry_service,
    get_webhook_service,
)
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
    """Create JSON HTTP response."""
    return func.HttpResponse(
        body=json.dumps(data, default=str),
        status_code=status_code,
        mimetype="application/json",
    )


def create_error_response(
    error: str,
    status_code: int = 500,
    details: dict[str, Any] | None = None,
) -> func.HttpResponse:
    """Create error JSON response."""
    body: dict[str, Any] = {
        "status": "error",
        "error": error,
    }
    if details:
        body["details"] = details

    return func.HttpResponse(
        body=json.dumps(body, default=str),
        status_code=status_code,
        mimetype="application/json",
    )


async def process_pdf_internal(
    blob_url: str,
    blob_name: str,
    model_id: str,
    webhook_url: str | None = None,
) -> dict[str, Any]:
    """Internal function to process a PDF document.

    Used by both HTTP trigger and blob trigger.

    Args:
        blob_url: URL to the PDF blob.
        blob_name: Blob path within container.
        model_id: Document Intelligence model ID.
        webhook_url: Optional webhook URL for completion notification.

    Returns:
        dict: Processing result with status, forms processed, etc.

    Raises:
        Various exceptions for different failure modes.
    """
    config = get_config()
    blob_service = get_blob_service()
    telemetry = get_telemetry_service()

    if not blob_service:
        raise BlobServiceError("Storage connection not configured")

    # Download the PDF to check if splitting is needed
    logger.info(f"Downloading PDF: {blob_name}")
    pdf_content = blob_service.download_blob(blob_url)

    # Check if PDF needs splitting
    pdf_service = get_pdf_service(pages_per_form=PAGES_PER_FORM)
    page_count = pdf_service.get_page_count(pdf_content)
    logger.info(f"PDF has {page_count} pages")

    # Parse original blob info
    container_name, original_blob_path = blob_service.parse_blob_url(blob_url)
    base_name = original_blob_path.rsplit(".", 1)[0]

    processed_at = datetime.now(timezone.utc).isoformat()
    doc_service = get_document_service()
    cosmos_service = get_cosmos_service()
    webhook_service = get_webhook_service()

    document_ids: list[str] = []

    if page_count <= PAGES_PER_FORM:
        # No splitting needed - process as single document
        logger.info("No splitting needed, processing as single form")

        with telemetry.track_operation("process_form", model_id) as op:
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
                "processedPdfUrl": blob_url,
                "processedAt": processed_at,
                "formNumber": 1,
                "totalForms": 1,
                **analysis_result,
            }

            await cosmos_service.save_document_result(document)
            document_ids.append(doc_id)

            op["status"] = "completed"
            op["confidence"] = analysis_result.get("modelConfidence")
            op["page_count"] = page_count

        # Send webhook notification
        if webhook_url or config.webhook_url:
            await webhook_service.notify_processing_complete(
                source_file=blob_name,
                status="completed",
                forms_processed=1,
                total_forms=1,
                document_ids=document_ids,
                webhook_url=webhook_url,
            )

        return {
            "status": "success",
            "documentId": doc_id,
            "processedAt": processed_at,
            "formsProcessed": 1,
        }

    # Split PDF into 2-page chunks
    logger.info(f"Splitting {page_count}-page PDF into {PAGES_PER_FORM}-page forms")
    chunks = pdf_service.split_pdf(pdf_content)
    total_forms = len(chunks)

    logger.info(f"Split into {total_forms} forms")

    # Process form chunks in parallel (limit concurrency to avoid rate limits)
    semaphore = asyncio.Semaphore(3)

    async def process_form(
        form_num: int,
        chunk_bytes: bytes,
        start_page: int,
        end_page: int,
    ) -> dict[str, Any]:
        """Process a single form chunk."""
        async with semaphore:
            chunk_blob_name = f"{base_name}_form{form_num}_pages{start_page}-{end_page}.pdf"
            split_blob_path = f"_splits/{chunk_blob_name}"

            logger.info(f"Processing form {form_num}/{total_forms}: pages {start_page}-{end_page}")

            try:
                with telemetry.track_operation("process_form", model_id) as op:
                    # Upload split PDF
                    chunk_url = blob_service.upload_blob(
                        container_name=container_name,
                        blob_name=split_blob_path,
                        content=chunk_bytes,
                    )

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
                        "sourceFile": blob_name,
                        "processedPdfUrl": chunk_url,
                        "processedAt": processed_at,
                        "formNumber": form_num,
                        "totalForms": total_forms,
                        "pageRange": f"{start_page}-{end_page}",
                        "originalPageCount": page_count,
                        **analysis_result,
                    }

                    await cosmos_service.save_document_result(document)

                    op["status"] = "completed"
                    op["confidence"] = analysis_result.get("modelConfidence")
                    op["page_count"] = end_page - start_page + 1

                    logger.info(f"Successfully processed form {form_num}")
                    return {
                        "formNumber": form_num,
                        "documentId": doc_id,
                        "pageRange": f"{start_page}-{end_page}",
                        "status": "success",
                    }

            except (DocumentProcessingError, RateLimitError) as e:
                logger.error(f"Failed to process form {form_num}: {e}")
                telemetry.track_form_processed(
                    model_id=model_id,
                    status="failed",
                    page_count=end_page - start_page + 1,
                )
                return {
                    "formNumber": form_num,
                    "pageRange": f"{start_page}-{end_page}",
                    "status": "failed",
                    "error": str(e),
                }

    # Create tasks for all forms
    tasks = [
        process_form(form_num, chunk_bytes, start_page, end_page)
        for form_num, (chunk_bytes, start_page, end_page) in enumerate(chunks, start=1)
    ]

    # Process all forms in parallel
    results = await asyncio.gather(*tasks)

    # Count successes and collect document IDs
    successful = 0
    for r in results:
        if r["status"] == "success":
            successful += 1
            document_ids.append(r["documentId"])

    status = "success" if successful == total_forms else "partial"

    # Send webhook notification
    if webhook_url or config.webhook_url:
        await webhook_service.notify_processing_complete(
            source_file=blob_name,
            status=status,
            forms_processed=successful,
            total_forms=total_forms,
            document_ids=document_ids,
            webhook_url=webhook_url,
        )

    return {
        "status": status,
        "processedAt": processed_at,
        "formsProcessed": successful,
        "totalForms": total_forms,
        "originalPageCount": page_count,
        "results": results,
    }


@app.function_name(name="ProcessDocument")
@app.route(route="process", methods=["POST"])
async def process_document(req: func.HttpRequest) -> func.HttpResponse:
    """Process a PDF document through Document Intelligence.

    Request body:
        {
            "blobUrl": "https://storage.blob.core.windows.net/container/file.pdf",
            "blobName": "folder/file.pdf",
            "modelId": "custom-model-v1",  // optional
            "webhookUrl": "https://example.com/webhook"  // optional
        }
    """
    logger.info("ProcessDocument HTTP trigger invoked")

    try:
        req_body = req.get_json()
    except ValueError:
        return create_error_response("Invalid JSON in request body", status_code=400)

    blob_url = req_body.get("blobUrl")
    blob_name = req_body.get("blobName")

    if not blob_url:
        return create_error_response("Missing required field: blobUrl", status_code=400)
    if not blob_name:
        return create_error_response("Missing required field: blobName", status_code=400)

    try:
        config = get_config()
        model_id = req_body.get("modelId", config.default_model_id)
        webhook_url = req_body.get("webhookUrl")

        # Validate model if custom
        doc_service = get_document_service()
        await doc_service.validate_model(model_id)

        result = await process_pdf_internal(
            blob_url=blob_url,
            blob_name=blob_name,
            model_id=model_id,
            webhook_url=webhook_url,
        )

        return create_response(result, status_code=200)

    except ConfigurationError as e:
        return create_error_response(f"Configuration error: {e}", status_code=500)

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
        return create_error_response("Internal server error", status_code=500)


@app.function_name(name="ReprocessDocument")
@app.route(route="reprocess/{blob_name}", methods=["POST"])
async def reprocess_document(req: func.HttpRequest) -> func.HttpResponse:
    """Reprocess a failed document.

    Path parameters:
        blob_name: URL-encoded blob path

    Request body (optional):
        {
            "modelId": "new-model-v2",  // optional override
            "force": true,  // reprocess even if completed
            "webhookUrl": "https://example.com/webhook"
        }
    """
    logger.info("ReprocessDocument HTTP trigger invoked")

    blob_name = req.route_params.get("blob_name")
    if not blob_name:
        return create_error_response("Missing blob_name in path", status_code=400)

    blob_name = unquote(blob_name)

    try:
        req_body = req.get_json() if req.get_body() else {}
    except ValueError:
        req_body = {}

    force = req_body.get("force", False)

    try:
        config = get_config()
        cosmos_service = get_cosmos_service()
        blob_service = get_blob_service()

        if not blob_service:
            return create_error_response("Storage connection not configured", status_code=500)

        # Check if document exists and get current status
        docs = await cosmos_service.query_by_source_file(blob_name)

        if not docs:
            return create_error_response(
                f"No documents found for {blob_name}",
                status_code=404,
            )

        # Check if already completed (unless force=true)
        if not force and all(d.get("status") == "completed" for d in docs):
            return create_error_response(
                "Document already completed. Use force=true to reprocess.",
                status_code=409,
            )

        # Check retry count for dead letter handling
        max_retries = config.max_retry_attempts
        retry_count = max(d.get("retryCount", 0) for d in docs)

        if retry_count >= max_retries and not force:
            # Move to dead letter queue
            telemetry = get_telemetry_service()
            telemetry.track_dead_letter(blob_name, f"Max retries ({max_retries}) exceeded")

            return create_error_response(
                f"Document exceeded max retries ({max_retries}). Use force=true to retry anyway.",
                status_code=410,
                details={"retryCount": retry_count},
            )

        # Get original blob URL
        # Reconstruct from storage account
        container_name = blob_name.split("/")[0] if "/" in blob_name else "pdfs"
        blob_path = blob_name if "/" in blob_name else f"incoming/{blob_name}"

        # Build blob URL
        account_name = blob_service.client.account_name
        blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_path}"

        # Increment retry count
        for doc in docs:
            if doc.get("status") == "failed":
                await cosmos_service.increment_retry_count(doc["id"], blob_name)

        model_id = req_body.get("modelId", config.default_model_id)
        webhook_url = req_body.get("webhookUrl")

        result = await process_pdf_internal(
            blob_url=blob_url,
            blob_name=blob_name,
            model_id=model_id,
            webhook_url=webhook_url,
        )

        result["retryCount"] = retry_count + 1
        return create_response(result, status_code=200)

    except Exception as e:
        logger.exception(f"Reprocess error: {e}")
        return create_error_response(f"Reprocess failed: {e}", status_code=500)


@app.function_name(name="GetDocumentStatus")
@app.route(route="status/{blob_name}", methods=["GET"])
async def get_document_status(req: func.HttpRequest) -> func.HttpResponse:
    """Get processing status for a document.

    Path parameters:
        blob_name: URL-encoded blob path
    """
    logger.info("GetDocumentStatus HTTP trigger invoked")

    blob_name = req.route_params.get("blob_name")
    if not blob_name:
        return create_error_response("Missing blob_name in path", status_code=400)

    blob_name = unquote(blob_name)

    try:
        cosmos_service = get_cosmos_service()
        doc_id = blob_name.replace("/", "_").replace(".", "_")

        doc = await cosmos_service.get_document(doc_id, blob_name)

        if doc:
            return create_response({
                "status": doc.get("status", "unknown"),
                "documentId": doc_id,
                "sourceFile": blob_name,
                "processedAt": doc.get("processedAt"),
                "formNumber": doc.get("formNumber"),
                "totalForms": doc.get("totalForms"),
            })
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
        return create_error_response(f"Database error: {e.reason}", status_code=500)

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return create_error_response("Internal server error", status_code=500)


@app.function_name(name="GetBatchStatus")
@app.route(route="status/batch/{blob_name}", methods=["GET"])
async def get_batch_status(req: func.HttpRequest) -> func.HttpResponse:
    """Get status of all forms from a multi-page PDF.

    Path parameters:
        blob_name: URL-encoded blob path (source file)
    """
    logger.info("GetBatchStatus HTTP trigger invoked")

    blob_name = req.route_params.get("blob_name")
    if not blob_name:
        return create_error_response("Missing blob_name in path", status_code=400)

    blob_name = unquote(blob_name)

    try:
        cosmos_service = get_cosmos_service()
        docs = await cosmos_service.query_by_source_file(blob_name)

        if not docs:
            return create_response(
                {
                    "status": "not_found",
                    "sourceFile": blob_name,
                    "totalForms": 0,
                    "documents": [],
                },
                status_code=404,
            )

        # Calculate stats
        completed = sum(1 for d in docs if d.get("status") == "completed")
        failed = sum(1 for d in docs if d.get("status") == "failed")
        pending = sum(1 for d in docs if d.get("status") in ("pending", "processing"))
        total_forms = docs[0].get("totalForms", len(docs)) if docs else 0

        # Build document list
        documents = [
            {
                "documentId": d.get("id"),
                "formNumber": d.get("formNumber"),
                "pageRange": d.get("pageRange"),
                "status": d.get("status"),
                "processedAt": d.get("processedAt"),
                "error": d.get("error"),
            }
            for d in docs
        ]

        return create_response({
            "sourceFile": blob_name,
            "totalForms": total_forms,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "documents": documents,
        })

    except CosmosError as e:
        logger.error(f"Cosmos DB error: {e}")
        return create_error_response(f"Database error: {e.reason}", status_code=500)

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return create_error_response("Internal server error", status_code=500)


@app.function_name(name="DeleteDocument")
@app.route(route="documents/{blob_name}", methods=["DELETE"])
async def delete_document(req: func.HttpRequest) -> func.HttpResponse:
    """Delete processed documents and optionally split PDFs.

    Path parameters:
        blob_name: URL-encoded blob path

    Query parameters:
        deleteSplits: Delete split PDFs from _splits/ (default: true)
        deleteOriginal: Delete original PDF (default: false)
    """
    logger.info("DeleteDocument HTTP trigger invoked")

    blob_name = req.route_params.get("blob_name")
    if not blob_name:
        return create_error_response("Missing blob_name in path", status_code=400)

    blob_name = unquote(blob_name)

    delete_splits = req.params.get("deleteSplits", "true").lower() == "true"
    delete_original = req.params.get("deleteOriginal", "false").lower() == "true"

    try:
        cosmos_service = get_cosmos_service()
        blob_service = get_blob_service()

        errors: list[str] = []
        deleted_blobs = 0

        # Delete Cosmos DB documents
        deleted_docs = await cosmos_service.delete_by_source_file(blob_name)

        # Delete split PDFs if requested
        if delete_splits and blob_service:
            try:
                container_name = blob_name.split("/")[0] if "/" in blob_name else "pdfs"
                base_name = blob_name.rsplit(".", 1)[0].rsplit("/", 1)[-1]

                # List and delete split blobs
                split_prefix = f"_splits/{base_name}_form"
                split_blobs = blob_service.list_blobs(container_name, prefix=split_prefix)

                for split_blob in split_blobs:
                    try:
                        blob_service.delete_blob(container_name, split_blob)
                        deleted_blobs += 1
                    except BlobServiceError as e:
                        errors.append(f"Failed to delete {split_blob}: {e.reason}")

            except BlobServiceError as e:
                errors.append(f"Failed to list split blobs: {e.reason}")

        # Delete original if requested
        if delete_original and blob_service:
            try:
                container_name, original_path = blob_service.parse_blob_url(
                    f"https://placeholder.blob.core.windows.net/{blob_name}"
                )
                blob_service.delete_blob(container_name, original_path)
                deleted_blobs += 1
            except BlobServiceError as e:
                errors.append(f"Failed to delete original: {e.reason}")

        return create_response({
            "status": "success" if not errors else "partial",
            "deletedDocuments": deleted_docs,
            "deletedBlobs": deleted_blobs,
            "errors": errors,
        })

    except CosmosError as e:
        logger.error(f"Cosmos DB error: {e}")
        return create_error_response(f"Database error: {e.reason}", status_code=500)

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return create_error_response("Internal server error", status_code=500)


@app.function_name(name="Health")
@app.route(route="health", methods=["GET"])
async def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint with service status."""
    services: dict[str, str] = {}
    blob_trigger_status: dict[str, Any] = {}

    # Check blob service
    try:
        blob_service = get_blob_service()
        services["storage"] = "healthy" if blob_service else "not_configured"

        # Check blob trigger health - verify storage connectivity
        if blob_service:
            try:
                # Try to list blobs in incoming folder to verify trigger path
                container_name = "pdfs"
                blobs = list(blob_service.list_blobs(container_name, prefix="incoming/"))
                blob_trigger_status = {
                    "status": "healthy",
                    "container": container_name,
                    "path": "incoming/",
                    "pendingFiles": len(blobs),
                }
            except Exception as e:
                blob_trigger_status = {
                    "status": "unhealthy",
                    "error": str(e),
                }
    except Exception:
        services["storage"] = "unhealthy"
        blob_trigger_status = {"status": "unknown", "error": "Storage not accessible"}

    # Check config
    try:
        config = get_config()
        services["config"] = "healthy"
        services["doc_intel"] = "configured" if config.doc_intel_endpoint else "not_configured"
        services["cosmos"] = "configured" if config.cosmos_endpoint else "not_configured"
    except Exception:
        services["config"] = "unhealthy"

    overall_status = "healthy" if all(
        s in ("healthy", "configured") for s in services.values()
    ) else "degraded"

    return create_response({
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "services": services,
        "blobTrigger": blob_trigger_status,
    })


@app.function_name(name="EstimateCost")
@app.route(route="estimate-cost", methods=["POST"])
async def estimate_cost(req: func.HttpRequest) -> func.HttpResponse:
    """Estimate Document Intelligence processing costs.

    Request body:
        {
            "blobUrl": "https://...",  // Optional: URL to PDF for page count
            "pageCount": 10,           // Optional: Manual page count
            "modelId": "custom-model"  // Optional: Model ID for pricing tier
        }

    Returns cost estimate based on Azure Document Intelligence pricing.
    """
    logger.info("EstimateCost HTTP trigger invoked")

    try:
        req_body = req.get_json()
    except ValueError:
        return create_error_response("Invalid JSON in request body", status_code=400)

    blob_url = req_body.get("blobUrl")
    page_count = req_body.get("pageCount")
    model_id = req_body.get("modelId", "prebuilt-layout")

    if not blob_url and not page_count:
        return create_error_response(
            "Either blobUrl or pageCount is required",
            status_code=400,
        )

    try:
        # Get page count from PDF if URL provided
        if blob_url and not page_count:
            blob_service = get_blob_service()
            if blob_service:
                pdf_content = blob_service.download_blob(blob_url)
                pdf_service = get_pdf_service()
                page_count = pdf_service.get_page_count(pdf_content)
            else:
                return create_error_response(
                    "Storage not configured, provide pageCount instead",
                    status_code=400,
                )

        # Determine model type for pricing
        if model_id.startswith("prebuilt-"):
            model_type = "prebuilt"
            price_per_page = 0.001  # $1.00 per 1000 pages for prebuilt
        else:
            model_type = "custom"
            price_per_page = 0.01  # $10.00 per 1000 pages for custom

        # Calculate forms count (assuming 2 pages per form)
        forms_count = (page_count + 1) // 2

        # Calculate costs
        read_cost = page_count * 0.001  # Read model for splitting
        analysis_cost = page_count * price_per_page
        total_cost = read_cost + analysis_cost

        notes = [
            f"Pricing based on Azure Document Intelligence standard tier",
            f"Prebuilt models: $1.00/1000 pages, Custom models: $10.00/1000 pages",
            f"Page splitting uses Read model ($1.00/1000 pages)",
        ]

        if page_count > 50:
            notes.append("Consider batch processing for volumes over 50 pages")

        return create_response({
            "pageCount": page_count,
            "formsCount": forms_count,
            "modelType": model_type,
            "pricing": {
                "readCostPerPage": 0.001,
                "analysisCostPerPage": price_per_page,
                "currency": "USD",
            },
            "estimatedCostUsd": round(total_cost, 4),
            "notes": notes,
        })

    except Exception as e:
        logger.exception(f"Cost estimation error: {e}")
        return create_error_response(f"Cost estimation failed: {e}", status_code=500)


@app.function_name(name="BatchProcess")
@app.route(route="batch", methods=["POST"])
async def batch_process(req: func.HttpRequest) -> func.HttpResponse:
    """Process multiple PDFs in a single request.

    Request body:
        {
            "blobs": [
                {"blobUrl": "https://...", "blobName": "doc1.pdf"},
                {"blobUrl": "https://...", "blobName": "doc2.pdf"}
            ],
            "modelId": "custom-model-v1",
            "webhookUrl": "https://...",
            "parallel": true
        }
    """
    logger.info("BatchProcess HTTP trigger invoked")

    try:
        req_body = req.get_json()
    except ValueError:
        return create_error_response("Invalid JSON in request body", status_code=400)

    blobs = req_body.get("blobs", [])
    if not blobs:
        return create_error_response("No blobs provided", status_code=400)

    if len(blobs) > 50:
        return create_error_response(
            "Maximum 50 blobs per batch request",
            status_code=400,
        )

    try:
        config = get_config()
        model_id = req_body.get("modelId", config.default_model_id)
        webhook_url = req_body.get("webhookUrl")
        parallel = req_body.get("parallel", True)

        # Generate batch ID
        batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        results: list[dict[str, Any]] = []

        async def process_single(blob_info: dict[str, str]) -> dict[str, Any]:
            """Process a single blob from the batch."""
            blob_url = blob_info.get("blobUrl", "")
            blob_name = blob_info.get("blobName", "")

            if not blob_url or not blob_name:
                return {
                    "blobName": blob_name or "unknown",
                    "status": "failed",
                    "error": "Missing blobUrl or blobName",
                }

            try:
                result = await process_pdf_internal(
                    blob_url=blob_url,
                    blob_name=blob_name,
                    model_id=model_id,
                    webhook_url=None,  # Webhook at batch level only
                )
                return {
                    "blobName": blob_name,
                    "status": result.get("status", "unknown"),
                    "formsProcessed": result.get("formsProcessed", 0),
                    "documentId": result.get("documentId"),
                }
            except Exception as e:
                logger.error(f"Batch item failed: {blob_name}: {e}")
                return {
                    "blobName": blob_name,
                    "status": "failed",
                    "error": str(e),
                }

        if parallel:
            # Process all blobs in parallel
            tasks = [process_single(blob) for blob in blobs]
            results = await asyncio.gather(*tasks)
        else:
            # Process sequentially
            for blob in blobs:
                result = await process_single(blob)
                results.append(result)

        # Count results
        processed = sum(1 for r in results if r.get("status") in ("success", "partial"))
        failed = sum(1 for r in results if r.get("status") == "failed")

        overall_status = "success" if failed == 0 else ("partial" if processed > 0 else "failed")

        # Send webhook notification for batch completion
        if webhook_url:
            webhook_service = get_webhook_service()
            await webhook_service.notify_processing_complete(
                source_file=batch_id,
                status=overall_status,
                forms_processed=processed,
                total_forms=len(blobs),
                document_ids=[r.get("documentId") for r in results if r.get("documentId")],
                webhook_url=webhook_url,
            )

        return create_response({
            "status": overall_status,
            "batchId": batch_id,
            "totalBlobs": len(blobs),
            "processed": processed,
            "failed": failed,
            "results": results,
        })

    except Exception as e:
        logger.exception(f"Batch processing error: {e}")
        return create_error_response(f"Batch processing failed: {e}", status_code=500)


@app.function_name(name="ProcessMultiModel")
@app.route(route="process-multi", methods=["POST"])
async def process_multi_model(req: func.HttpRequest) -> func.HttpResponse:
    """Process a PDF using different models for different page ranges.

    Request body:
        {
            "blobUrl": "https://...",
            "blobName": "document.pdf",
            "modelMapping": {
                "1-2": "form-type-a-model",
                "3-4": "form-type-b-model",
                "5-6": "form-type-c-model"
            },
            "webhookUrl": "https://..."
        }
    """
    logger.info("ProcessMultiModel HTTP trigger invoked")

    try:
        req_body = req.get_json()
    except ValueError:
        return create_error_response("Invalid JSON in request body", status_code=400)

    blob_url = req_body.get("blobUrl")
    blob_name = req_body.get("blobName")
    model_mapping = req_body.get("modelMapping", {})
    webhook_url = req_body.get("webhookUrl")

    if not blob_url or not blob_name:
        return create_error_response(
            "Missing required fields: blobUrl and blobName",
            status_code=400,
        )

    if not model_mapping:
        return create_error_response(
            "modelMapping is required for multi-model processing",
            status_code=400,
        )

    try:
        blob_service = get_blob_service()
        if not blob_service:
            return create_error_response("Storage not configured", status_code=500)

        # Download and split PDF
        pdf_content = blob_service.download_blob(blob_url)
        pdf_service = get_pdf_service()
        page_count = pdf_service.get_page_count(pdf_content)

        doc_service = get_document_service()
        cosmos_service = get_cosmos_service()
        webhook_service = get_webhook_service()

        container_name, original_blob_path = blob_service.parse_blob_url(blob_url)
        base_name = original_blob_path.rsplit(".", 1)[0]
        processed_at = datetime.now(timezone.utc).isoformat()

        results: list[dict[str, Any]] = []
        document_ids: list[str] = []

        # Parse and process each page range
        for page_range, model_id in model_mapping.items():
            try:
                # Parse page range (e.g., "1-2" -> start=1, end=2)
                parts = page_range.split("-")
                start_page = int(parts[0])
                end_page = int(parts[1]) if len(parts) > 1 else start_page

                if start_page < 1 or end_page > page_count:
                    results.append({
                        "pageRange": page_range,
                        "modelId": model_id,
                        "status": "failed",
                        "error": f"Page range {page_range} out of bounds (document has {page_count} pages)",
                    })
                    continue

                # Extract pages for this range
                chunk_bytes = pdf_service.extract_pages(pdf_content, start_page, end_page)

                # Upload chunk
                chunk_blob_name = f"{base_name}_pages{start_page}-{end_page}.pdf"
                split_blob_path = f"_splits/{chunk_blob_name}"
                chunk_url = blob_service.upload_blob(
                    container_name=container_name,
                    blob_name=split_blob_path,
                    content=chunk_bytes,
                )

                # Process with specified model
                chunk_sas_url = blob_service.generate_sas_url(chunk_url)
                analysis_result = await doc_service.analyze_document(
                    blob_url=chunk_sas_url,
                    model_id=model_id,
                    blob_name=f"{blob_name} (pages {start_page}-{end_page})",
                )

                # Save to Cosmos DB
                doc_id = f"{blob_name.replace('/', '_').replace('.', '_')}_pages{start_page}-{end_page}"
                document = {
                    "id": doc_id,
                    "sourceFile": blob_name,
                    "processedPdfUrl": chunk_url,
                    "processedAt": processed_at,
                    "pageRange": page_range,
                    "originalPageCount": page_count,
                    **analysis_result,
                }

                await cosmos_service.save_document_result(document)
                document_ids.append(doc_id)

                results.append({
                    "pageRange": page_range,
                    "modelId": model_id,
                    "documentId": doc_id,
                    "status": "success",
                })

            except Exception as e:
                logger.error(f"Failed to process pages {page_range}: {e}")
                results.append({
                    "pageRange": page_range,
                    "modelId": model_id,
                    "status": "failed",
                    "error": str(e),
                })

        # Calculate status
        successful = sum(1 for r in results if r.get("status") == "success")
        status = "success" if successful == len(results) else (
            "partial" if successful > 0 else "failed"
        )

        # Send webhook notification
        if webhook_url:
            await webhook_service.notify_processing_complete(
                source_file=blob_name,
                status=status,
                forms_processed=successful,
                total_forms=len(results),
                document_ids=document_ids,
                webhook_url=webhook_url,
            )

        return create_response({
            "status": status,
            "processedAt": processed_at,
            "pageCount": page_count,
            "rangesProcessed": successful,
            "totalRanges": len(results),
            "results": results,
        })

    except Exception as e:
        logger.exception(f"Multi-model processing error: {e}")
        return create_error_response(f"Multi-model processing failed: {e}", status_code=500)


# ============================================================================
# Blob Trigger for Auto-Processing
# ============================================================================


@app.function_name(name="ProcessBlobTrigger")
@app.blob_trigger(
    arg_name="blob",
    path="pdfs/incoming/{name}",
    connection="AzureWebJobsStorage",
)
async def process_blob_trigger(blob: func.InputStream) -> None:
    """Auto-process PDFs when uploaded to incoming/ folder.

    Triggered when a new blob is uploaded to: pdfs/incoming/

    Args:
        blob: Input stream with blob metadata and content.
    """
    blob_name = blob.name
    logger.info(f"Blob trigger activated for: {blob_name}")

    if not blob_name or not blob_name.lower().endswith(".pdf"):
        logger.info(f"Skipping non-PDF file: {blob_name}")
        return

    try:
        config = get_config()
        blob_service = get_blob_service()
        telemetry = get_telemetry_service()
        webhook_service = get_webhook_service()

        if not blob_service:
            logger.error("Storage connection not configured for blob trigger")
            return

        # Build blob URL from trigger metadata
        account_name = blob_service.client.account_name
        # blob.name is like "pdfs/incoming/document.pdf"
        blob_url = f"https://{account_name}.blob.core.windows.net/{blob_name}"

        # Extract just the filename for sourceFile
        source_file = blob_name.split("/", 1)[1] if "/" in blob_name else blob_name

        logger.info(f"Processing blob: {blob_url}")

        result = await process_pdf_internal(
            blob_url=blob_url,
            blob_name=source_file,
            model_id=config.default_model_id,
            webhook_url=config.webhook_url,
        )

        logger.info(f"Blob trigger processing complete: {result.get('status')}")

    except Exception as e:
        logger.exception(f"Blob trigger processing failed: {e}")

        # Track failure and potentially move to dead letter
        try:
            telemetry = get_telemetry_service()
            telemetry.track_form_processed(
                model_id="unknown",
                status="failed",
            )

            # Save error document
            cosmos_service = get_cosmos_service()
            doc_id = blob_name.replace("/", "_").replace(".", "_")
            await cosmos_service.save_document_result({
                "id": doc_id,
                "sourceFile": blob_name,
                "processedAt": datetime.now(timezone.utc).isoformat(),
                "status": "failed",
                "error": str(e),
                "fields": {},
                "confidence": {},
            })

        except Exception as save_error:
            logger.error(f"Failed to save error state: {save_error}")
