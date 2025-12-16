"""Document management endpoints with Azure Storage and AI Search.

Handles persistent document storage in Azure Blob Storage, metadata management,
and integration with Azure AI Search for indexing uploaded documents.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from io import BytesIO

from fastapi import APIRouter, UploadFile, File, HTTPException, status, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.services.azure_storage import get_azure_storage_service
from app.services.azure_search import get_azure_search_service
from app.workflow.pdf_processor import get_pdf_processor
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document as LangChainDocument

logger = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])

# Pydantic models
class DocumentMetadata(BaseModel):
    id: str
    filename: str
    original_filename: str
    category: str
    size: int
    content_type: str
    upload_date: datetime
    indexed: bool = False
    blob_name: str
    blob_url: str
    metadata: Dict[str, Any] = {}

class DocumentUploadResponse(BaseModel):
    success: bool
    documents: List[DocumentMetadata]
    message: str

class DocumentListResponse(BaseModel):
    documents: List[DocumentMetadata]
    total: int

class StatusResponse(BaseModel):
    success: bool
    message: str

class DocumentResponse(BaseModel):
    document: DocumentMetadata
    download_url: Optional[str] = None

# In-memory metadata cache (could be replaced with Azure Cosmos DB or Table Storage)
_metadata_cache: Dict[str, DocumentMetadata] = {}
_cache_initialized = False


def _initialize_cache_from_storage():
    """Initialize metadata cache from Azure Blob Storage on first access."""
    global _cache_initialized
    if _cache_initialized:
        return
    
    try:
        storage_service = get_azure_storage_service()
        blobs = storage_service.list_documents()
        
        for blob in blobs:
            blob_name = blob["blob_name"]
            # Extract document ID from blob name (format: category/uuid.ext)
            parts = blob_name.split('/')
            if len(parts) == 2:
                filename = parts[1]
                doc_id = Path(filename).stem  # Get UUID without extension
                
                # Get metadata from blob
                blob_metadata = blob.get("metadata", {})
                
                # Create metadata from blob properties
                doc_metadata = DocumentMetadata(
                    id=doc_id,
                    filename=filename,
                    original_filename=blob_metadata.get("original_filename", filename),
                    category=blob_metadata.get("category", parts[0]),
                    size=blob.get("size", 0),
                    content_type=blob.get("content_type", "application/octet-stream"),
                    upload_date=blob.get("created", datetime.now()),
                    indexed=True,  # Assume migrated documents are indexed
                    blob_name=blob_name,
                    blob_url=f"https://{storage_service.account_name}.blob.core.windows.net/{storage_service.container_name}/{blob_name}",
                    metadata=blob_metadata
                )
                _metadata_cache[doc_id] = doc_metadata
        
        _cache_initialized = True
        logger.info(f"Initialized metadata cache with {len(_metadata_cache)} documents from Azure Blob Storage")
        
    except Exception as e:
        logger.error(f"Failed to initialize cache from storage: {e}", exc_info=True)
        _cache_initialized = True  # Set to true anyway to avoid repeated failures


# API endpoints
@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_documents_for_indexing(
    files: List[UploadFile] = File(...),
    category: str = Query("policy", description="Document category: policy, regulation, or reference"),
    auto_index: bool = Query(True, description="Automatically add to search index")
) -> DocumentUploadResponse:
    """Upload documents to Azure Blob Storage with optional AI Search indexing.
    
    Documents are stored in Azure Blob Storage and can be automatically
    added to the Azure AI Search index for policy queries.
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded")
    
    if category not in ["policy", "regulation", "reference"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category")
    
    storage_service = get_azure_storage_service()
    uploaded_docs = []
    
    for upload in files:
        try:
            # Validate file
            if not upload.filename:
                continue
                
            # Check file type
            file_extension = Path(upload.filename).suffix.lower()
            allowed_extensions = {'.txt', '.md', '.pdf', '.doc', '.docx'}
            
            if file_extension not in allowed_extensions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File \"{upload.filename}\" has an unsupported format. Supported formats: PDF, Markdown, Text, Word documents."
                )
            
            # Read file content
            file_content = await upload.read()
            file_data = BytesIO(file_content)
            
            # Validate PDF files
            if file_extension == '.pdf':
                pdf_processor = get_pdf_processor()
                # Save temporarily to validate
                temp_path = Path(f"/tmp/{uuid.uuid4()}{file_extension}")
                try:
                    with open(temp_path, 'wb') as f:
                        f.write(file_content)
                    if not pdf_processor.is_valid_pdf(temp_path):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"File \"{upload.filename}\" is not a valid PDF or cannot be processed."
                        )
                finally:
                    if temp_path.exists():
                        temp_path.unlink()
            
            # Upload to Azure Blob Storage
            blob_name, blob_url = storage_service.upload_document(
                file_data=file_data,
                filename=upload.filename,
                category=category,
                content_type=upload.content_type or "application/octet-stream"
            )
            
            # Create metadata
            doc_id = blob_name.split('/')[1].split('.')[0]  # Extract UUID from blob_name
            doc_metadata = DocumentMetadata(
                id=doc_id,
                filename=Path(blob_name).name,
                original_filename=upload.filename,
                category=category,
                size=len(file_content),
                content_type=upload.content_type or "application/octet-stream",
                upload_date=datetime.now(),
                indexed=False,
                blob_name=blob_name,
                blob_url=blob_url
            )
            
            _metadata_cache[doc_id] = doc_metadata
            uploaded_docs.append(doc_metadata)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to upload {upload.filename}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload {upload.filename}: {str(e)}"
            )
        finally:
            await upload.close()
    
    # Auto-index if requested
    if auto_index and uploaded_docs:
        try:
            search_service = get_azure_search_service()
            indexed_count = 0
            
            for doc in uploaded_docs:
                # Download document from blob storage
                blob_content = storage_service.download_document(doc.blob_name)
                
                # Convert to LangChain documents
                langchain_docs = []
                file_extension = Path(doc.filename).suffix.lower()
                
                if file_extension == '.pdf':
                    # Save temporarily for PDF processing
                    temp_path = Path(f"/tmp/{doc.id}{file_extension}")
                    try:
                        with open(temp_path, 'wb') as f:
                            f.write(blob_content)
                        pdf_processor = get_pdf_processor()
                        langchain_docs = pdf_processor.pdf_to_langchain_documents(temp_path, chunk_pages=False)
                    finally:
                        if temp_path.exists():
                            temp_path.unlink()
                            
                elif file_extension in ['.txt', '.md']:
                    # Process text files
                    content = blob_content.decode('utf-8')
                    langchain_docs = [LangChainDocument(
                        page_content=content,
                        metadata={"source": doc.original_filename}
                    )]
                
                if langchain_docs:
                    # Add to search index
                    chunks_indexed = search_service.add_documents(langchain_docs, blob_name=doc.blob_name)
                    if chunks_indexed > 0:
                        _metadata_cache[doc.id].indexed = True
                        indexed_count += 1
                        logger.info(f"Indexed document: {doc.original_filename} ({chunks_indexed} chunks)")
            
            if indexed_count > 0:
                logger.info(f"Successfully indexed {indexed_count} out of {len(uploaded_docs)} documents")
            
        except Exception as e:
            logger.error(f"Failed to auto-index documents: {e}")
            # Don't fail upload if indexing fails
    
    return DocumentUploadResponse(
        success=True,
        documents=uploaded_docs,
        message=f"Successfully uploaded {len(uploaded_docs)} document(s) to Azure Blob Storage"
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    category: Optional[str] = Query(None, description="Filter by category"),
    indexed_only: bool = Query(False, description="Show only indexed documents")
) -> DocumentListResponse:
    """List all uploaded documents with optional filtering."""
    # Initialize cache from Azure Storage on first access
    _initialize_cache_from_storage()
    
    documents = list(_metadata_cache.values())
    
    # Apply filters
    if category:
        documents = [doc for doc in documents if doc.category == category]
    
    if indexed_only:
        documents = [doc for doc in documents if doc.indexed]
    
    # Sort by upload date (newest first)
    documents.sort(key=lambda x: x.upload_date, reverse=True)
    
    return DocumentListResponse(
        documents=documents,
        total=len(documents)
    )


@router.delete("/documents/{document_id}", response_model=StatusResponse)
async def delete_document(document_id: str) -> StatusResponse:
    """Delete a document from Azure Blob Storage and search index."""
    if document_id not in _metadata_cache:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    doc_metadata = _metadata_cache[document_id]
    
    try:
        # Delete from blob storage
        storage_service = get_azure_storage_service()
        storage_service.delete_document(doc_metadata.blob_name)
        
        # Delete from search index if indexed
        if doc_metadata.indexed:
            search_service = get_azure_search_service()
            search_service.delete_documents_by_blob(doc_metadata.blob_name)
        
        # Remove from metadata cache
        del _metadata_cache[document_id]
        
        return StatusResponse(
            success=True,
            message=f"Document {doc_metadata.original_filename} deleted successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str) -> DocumentResponse:
    """Get document metadata and SAS URL for download."""
    if document_id not in _metadata_cache:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    doc_metadata = _metadata_cache[document_id]
    
    # Generate SAS URL for secure download (valid for 1 hour)
    storage_service = get_azure_storage_service()
    sas_url = storage_service.generate_sas_url(doc_metadata.blob_name, expiry_hours=1)
    
    return DocumentResponse(
        document=doc_metadata,
        download_url=sas_url
    )


@router.get("/documents/{document_id}/download")
async def download_document(document_id: str):
    """Download a document file from Azure Blob Storage."""
    if document_id not in _metadata_cache:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    doc_metadata = _metadata_cache[document_id]
    
    try:
        storage_service = get_azure_storage_service()
        blob_content = storage_service.download_document(doc_metadata.blob_name)
        
        return Response(
            content=blob_content,
            media_type=doc_metadata.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{doc_metadata.original_filename}"'
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to download document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download document: {str(e)}"
        )


@router.post("/documents/{document_id}/index", response_model=StatusResponse)
async def index_document(document_id: str) -> StatusResponse:
    """Manually add a specific document to the Azure AI Search index."""
    if document_id not in _metadata_cache:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    doc_metadata = _metadata_cache[document_id]
    
    try:
        storage_service = get_azure_storage_service()
        search_service = get_azure_search_service()
        
        # Download document
        blob_content = storage_service.download_document(doc_metadata.blob_name)
        
        # Convert to LangChain documents
        langchain_docs = []
        file_extension = Path(doc_metadata.filename).suffix.lower()
        
        if file_extension == '.pdf':
            temp_path = Path(f"/tmp/{doc_metadata.id}{file_extension}")
            try:
                with open(temp_path, 'wb') as f:
                    f.write(blob_content)
                pdf_processor = get_pdf_processor()
                langchain_docs = pdf_processor.pdf_to_langchain_documents(temp_path, chunk_pages=False)
            finally:
                if temp_path.exists():
                    temp_path.unlink()
                    
        elif file_extension in ['.txt', '.md']:
            content = blob_content.decode('utf-8')
            langchain_docs = [LangChainDocument(
                page_content=content,
                metadata={"source": doc_metadata.original_filename}
            )]
        
        if langchain_docs:
            chunks_indexed = search_service.add_documents(langchain_docs, blob_name=doc_metadata.blob_name)
            _metadata_cache[document_id].indexed = True
            
            return StatusResponse(
                success=True,
                message=f"Document '{doc_metadata.original_filename}' successfully added to search index ({chunks_indexed} chunks)"
            )
        else:
            return StatusResponse(
                success=False,
                message=f"Failed to extract content from '{doc_metadata.original_filename}'"
            )
            
    except Exception as e:
        logger.error(f"Error indexing document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to index document: {str(e)}"
        )


# ============================================================================
# Content Understanding Endpoints
# ============================================================================

@router.post("/documents/analyze")
async def analyze_document_with_content_understanding(
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Analyze an uploaded document using Azure Content Understanding.
    
    Extracts key-value pairs, tables, and provides confidence scores
    for each extracted field. This endpoint is designed for testing
    Content Understanding capabilities before integrating into workflows.
    
    Args:
        file: The document file to analyze (PDF, PNG, JPG, TIFF)
        
    Returns:
        Dictionary containing:
        - extracted_fields: Key-value pairs found in the document
        - confidence_scores: Confidence score (0-1) for each field
        - tables: Any tables found in the document
        - content_preview: First 500 chars of extracted text
        - field_count: Number of fields extracted
        - table_count: Number of tables found
    """
    from app.services.content_understanding_service import get_content_understanding_service
    
    # Validate file type
    allowed_types = [
        "application/pdf",
        "image/png", 
        "image/jpeg",
        "image/tiff"
    ]
    
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Supported types: PDF, PNG, JPG, TIFF"
        )
    
    # Check file size (max 20MB)
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 20MB"
        )
    
    # Get Content Understanding service
    cu_service = get_content_understanding_service()
    
    if not cu_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Content Understanding service not configured. Please add AZURE_CONTENT_UNDERSTANDING_* environment variables."
        )
    
    try:
        logger.info(f"Analyzing document with Content Understanding: {file.filename} ({len(content)} bytes)")
        
        # Analyze the document
        result = await cu_service.analyze_claim_document(
            file_data=content,
            filename=file.filename
        )
        
        logger.info(f"Analysis complete: {result['field_count']} fields, {result['table_count']} tables")
        
        # Add helpful guidance if no fields were extracted
        if result['field_count'] == 0 and result['table_count'] == 0:
            logger.warning(
                "No fields or tables extracted. This usually means the analyzer needs to be trained. "
                "Options: 1) Use a prebuilt analyzer (prebuilt-document, prebuilt-invoice, prebuilt-receipt), "
                "2) Train a custom analyzer in Azure AI Studio with sample documents."
            )
            result['message'] = (
                "Analysis completed but no structured data was extracted. "
                "The analyzer may need to be trained with sample documents in Azure AI Studio, "
                "or you can use a prebuilt analyzer like 'prebuilt-document' or 'prebuilt-invoice'."
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Document analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Document analysis failed: {str(e)}"
        )


@router.get("/documents/analyzer-status")
async def get_content_understanding_status() -> Dict[str, Any]:
    """
    Check if Content Understanding is configured and available.
    
    Returns:
        Dictionary with:
        - available: Whether the service is ready
        - configured: Whether environment variables are set
        - endpoint: The configured endpoint (if available)
        - analyzer_id: The configured analyzer ID (if available)
    """
    from app.services.content_understanding_service import get_content_understanding_service
    from app.core.config import get_settings
    
    cu_service = get_content_understanding_service()
    settings = get_settings()
    
    configured = all([
        settings.azure_content_understanding_endpoint,
        settings.azure_content_understanding_key,
        settings.azure_content_understanding_analyzer_id
    ])
    
    return {
        "available": cu_service.is_available(),
        "configured": configured,
        "endpoint": settings.azure_content_understanding_endpoint if configured else None,
        "analyzer_id": settings.azure_content_understanding_analyzer_id if configured else None
    }
