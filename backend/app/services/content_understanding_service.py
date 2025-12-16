"""Azure Content Understanding Service for document analysis."""
import logging
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass

import requests
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class AnalysisResult:
    """Result from Content Understanding analysis."""
    status: str
    key_value_pairs: Dict[str, Any]
    tables: list
    content: str
    confidence_scores: Dict[str, float]
    raw_result: Dict[str, Any]


class ContentUnderstandingClient:
    """Client for Azure Content Understanding API."""
    
    def __init__(
        self,
        endpoint: str,
        subscription_key: str,
        api_version: str = "2025-05-01-preview"
    ):
        if not endpoint:
            raise ValueError("Endpoint must be provided")
        if not subscription_key:
            raise ValueError("Subscription key must be provided")
        
        self._endpoint = endpoint.rstrip("/")
        self._api_version = api_version
        self._headers = {
            "Ocp-Apim-Subscription-Key": subscription_key,
            "x-ms-useragent": "insurance-multi-agent"
        }
        self._logger = logging.getLogger(__name__)
    
    def begin_analyze(self, analyzer_id: str, file_data: bytes, content_type: str = "application/pdf") -> requests.Response:
        """
        Begin analysis of a document.
        
        Args:
            analyzer_id: The ID of the analyzer to use
            file_data: The binary file data
            content_type: The MIME type of the file
            
        Returns:
            Response from the analysis request
        """
        url = f"{self._endpoint}/contentunderstanding/analyzers/{analyzer_id}:analyze?api-version={self._api_version}&stringEncoding=utf16"
        
        headers = self._headers.copy()
        headers["Content-Type"] = "application/octet-stream"
        
        self._logger.info(f"Starting analysis with analyzer: '{analyzer_id}'")
        self._logger.info(f"Request URL: {url}")
        self._logger.info(f"File size: {len(file_data)} bytes")
        
        response = requests.post(url, headers=headers, data=file_data)
        
        # Log response details
        self._logger.info(f"Analysis request status: {response.status_code}")
        if response.status_code != 202:
            self._logger.warning(f"Unexpected status code: {response.status_code}, body: {response.text}")
        
        response.raise_for_status()
        
        return response
    
    def poll_result(
        self,
        response: requests.Response,
        timeout_seconds: int = 120,
        polling_interval_seconds: int = 2
    ) -> Dict[str, Any]:
        """
        Poll for analysis result until complete.
        
        Args:
            response: Initial response from begin_analyze
            timeout_seconds: Maximum time to wait
            polling_interval_seconds: Time between polls
            
        Returns:
            Analysis result dictionary
        """
        operation_location = response.headers.get("operation-location", "")
        if not operation_location:
            raise ValueError("Operation location not found in response headers")
        
        headers = self._headers.copy()
        headers["Content-Type"] = "application/json"
        
        start_time = time.time()
        while True:
            elapsed_time = time.time() - start_time
            
            if elapsed_time > timeout_seconds:
                raise TimeoutError(f"Operation timed out after {timeout_seconds:.2f} seconds")
            
            poll_response = requests.get(operation_location, headers=headers)
            poll_response.raise_for_status()
            result = poll_response.json()
            
            status = result.get("status", "")
            self._logger.info(f"Poll status: '{status}' (raw), top-level keys: {list(result.keys())}")
            status_lower = status.lower()
            
            if status_lower == "succeeded":
                self._logger.info(f"Analysis completed after {elapsed_time:.2f} seconds")
                
                # Log ALL top-level keys in the response
                self._logger.info(f"Full response top-level keys: {list(result.keys())}")
                
                # The 2025-05-01-preview API uses 'result' instead of 'analyzeResult'
                # Check for 'result' first, then fall back to 'analyzeResult'
                analyze_result = result.get('result') or result.get('analyzeResult', {})
                self._logger.info(f"analyze_result type: {type(analyze_result)}, keys: {list(analyze_result.keys()) if isinstance(analyze_result, dict) else 'N/A'}")
                
                # If analyze_result is empty, log the entire response
                if not analyze_result or (isinstance(analyze_result, dict) and len(analyze_result) == 0):
                    self._logger.error(f"analyze_result is empty or missing! Full response: {result}")
                
                # Check for documents array (newer API format)
                if 'documents' in analyze_result:
                    docs = analyze_result['documents']
                    self._logger.info(f"Found {len(docs)} document(s) in analyzeResult")
                    if docs and len(docs) > 0:
                        doc_fields = docs[0].get('fields', {})
                        self._logger.info(f"Document[0] has {len(doc_fields)} fields: {list(doc_fields.keys())}")
                
                # Check for fields at root level (older API format)
                if 'fields' in analyze_result:
                    self._logger.info(f"Fields at root level: {list(analyze_result['fields'].keys())}")
                
                return result
            elif status_lower == "failed":
                error_msg = result.get("error", {}).get("message", "Unknown error")
                self._logger.error(f"Analysis failed: {error_msg}")
                raise RuntimeError(f"Analysis failed: {error_msg}")
            else:
                self._logger.info(f"Analysis in progress... ({elapsed_time:.1f}s)")
            
            time.sleep(polling_interval_seconds)
    
    def analyze_document(
        self,
        analyzer_id: str,
        file_data: bytes,
        content_type: str = "application/pdf"
    ) -> AnalysisResult:
        """
        Analyze a document and return structured results.
        
        Args:
            analyzer_id: The ID of the analyzer to use
            file_data: The binary file data
            content_type: The MIME type of the file
            
        Returns:
            AnalysisResult with extracted data
        """
        # Begin analysis
        response = self.begin_analyze(analyzer_id, file_data, content_type)
        
        # Poll for result
        raw_result = self.poll_result(response)
        
        # Parse and structure the result
        return self._parse_result(raw_result)
    
    def _parse_result(self, raw_result: Dict[str, Any]) -> AnalysisResult:
        """Parse raw API result into structured format."""
        # The 2025-05-01-preview API uses 'result' instead of 'analyzeResult'
        analyze_result = raw_result.get("result") or raw_result.get("analyzeResult", {})
        
        logger.info(f"Parsing result - analyze_result keys: {list(analyze_result.keys())}")
        
        # Extract key-value pairs
        key_value_pairs = {}
        confidence_scores = {}
        
        # Try contents array first (newest API format for 2025-05-01-preview)
        if "contents" in analyze_result and analyze_result["contents"]:
            logger.info("Using contents array format (2025 API)")
            content = analyze_result["contents"][0]  # Get first content
            fields_dict = content.get("fields", {})
            logger.info(f"Found {len(fields_dict)} fields in contents[0]")
            
            for field_name, field_data in fields_dict.items():
                if isinstance(field_data, dict):
                    # Handle different field value structures - check each type explicitly
                    value = None
                    field_type = field_data.get("type", "unknown")
                    
                    if "valueString" in field_data:
                        value = field_data["valueString"]
                    elif "valueNumber" in field_data:
                        value = field_data["valueNumber"]
                    elif "valueDate" in field_data:
                        value = field_data["valueDate"]
                    elif "valueArray" in field_data:
                        # Handle array fields (e.g., damaged_items)
                        value = field_data["valueArray"]
                        logger.info(f"Found array field '{field_name}' with {len(value)} items")
                    elif "valueObject" in field_data:
                        # Handle object fields
                        value = field_data["valueObject"]
                    elif "content" in field_data:
                        value = field_data["content"]
                    elif "value" in field_data:
                        value = field_data["value"]
                    else:
                        logger.warning(f"Field '{field_name}' has unknown structure: type={field_type}, keys={list(field_data.keys())}")
                    
                    confidence = field_data.get("confidence", 1.0)
                else:
                    value = field_data
                    confidence = 1.0
                
                if value is not None and value != "":  # Skip empty strings but allow 0, False, etc.
                    key_value_pairs[field_name] = value
                    confidence_scores[field_name] = confidence
                    logger.info(f"Extracted field '{field_name}' (type: {field_type}): {str(value)[:50]}... (confidence: {confidence:.2f})")
                elif value == "":
                    logger.info(f"Skipping empty field '{field_name}'")
        
        # Try documents array (older 2024 API format)
        elif "documents" in analyze_result and analyze_result["documents"]:
            logger.info("Using documents array format (2024 API)")
            doc = analyze_result["documents"][0]  # Get first document
            fields_dict = doc.get("fields", {})
            logger.info(f"Found {len(fields_dict)} fields in document")
            
            for field_name, field_data in fields_dict.items():
                if isinstance(field_data, dict):
                    # Check each type explicitly
                    value = None
                    if "valueString" in field_data:
                        value = field_data["valueString"]
                    elif "valueNumber" in field_data:
                        value = field_data["valueNumber"]
                    elif "valueDate" in field_data:
                        value = field_data["valueDate"]
                    elif "content" in field_data:
                        value = field_data["content"]
                    elif "value" in field_data:
                        value = field_data["value"]
                    
                    confidence = field_data.get("confidence", 0.0)
                else:
                    value = field_data
                    confidence = 1.0
                
                if value is not None and value != "":
                    key_value_pairs[field_name] = value
                    confidence_scores[field_name] = confidence
                    logger.info(f"Extracted field '{field_name}': {str(value)[:50]}... (confidence: {confidence:.2f})")
        
        # Fall back to root level fields (oldest API format)
        elif "fields" in analyze_result:
            logger.info("Using root-level fields format (legacy API)")
            logger.info(f"Found {len(analyze_result['fields'])} fields in analyzeResult")
            for field_name, field_data in analyze_result["fields"].items():
                if isinstance(field_data, dict):
                    # Check each type explicitly
                    value = None
                    if "valueString" in field_data:
                        value = field_data["valueString"]
                    elif "valueNumber" in field_data:
                        value = field_data["valueNumber"]
                    elif "valueDate" in field_data:
                        value = field_data["valueDate"]
                    elif "content" in field_data:
                        value = field_data["content"]
                    elif "value" in field_data:
                        value = field_data["value"]
                    
                    confidence = field_data.get("confidence", 0.0)
                else:
                    value = field_data
                    confidence = 1.0
                
                if value is not None and value != "":
                    key_value_pairs[field_name] = value
                    confidence_scores[field_name] = confidence
        else:
            logger.warning("No fields found in 'contents', 'documents', or root 'fields' object")
        
        # Extract tables - check multiple possible locations
        tables = []
        
        # Try contents array first (2025 API)
        if "contents" in analyze_result and analyze_result["contents"]:
            content_item = analyze_result["contents"][0]
            if "tables" in content_item:
                logger.info(f"Found {len(content_item['tables'])} tables in contents[0]")
                for table in content_item["tables"]:
                    table_data = {
                        "row_count": table.get("rowCount", 0),
                        "column_count": table.get("columnCount", 0),
                        "cells": table.get("cells", [])
                    }
                    tables.append(table_data)
                    logger.info(f"Extracted table: {table_data['row_count']}x{table_data['column_count']} with {len(table_data['cells'])} cells")
        
        # Fall back to root-level tables (older API)
        if not tables and "tables" in analyze_result:
            logger.info(f"Found {len(analyze_result['tables'])} tables at root level")
            for table in analyze_result["tables"]:
                table_data = {
                    "row_count": table.get("rowCount", 0),
                    "column_count": table.get("columnCount", 0),
                    "cells": table.get("cells", [])
                }
                tables.append(table_data)
        
        # Extract content
        content = analyze_result.get("content", "")
        
        return AnalysisResult(
            status=raw_result.get("status", "unknown"),
            key_value_pairs=key_value_pairs,
            tables=tables,
            content=content,
            confidence_scores=confidence_scores,
            raw_result=raw_result
        )


class ContentUnderstandingService:
    """Service for document analysis using Azure Content Understanding."""
    
    def __init__(self):
        self._client: Optional[ContentUnderstandingClient] = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization of the client."""
        if self._initialized:
            return
        
        if not all([
            settings.azure_content_understanding_endpoint,
            settings.azure_content_understanding_key,
            settings.azure_content_understanding_analyzer_id
        ]):
            logger.warning("Content Understanding not configured - service unavailable")
            self._initialized = True
            return
        
        try:
            self._client = ContentUnderstandingClient(
                endpoint=settings.azure_content_understanding_endpoint,
                subscription_key=settings.azure_content_understanding_key
            )
            self._initialized = True
            logger.info("Content Understanding service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Content Understanding: {e}")
            self._initialized = True
    
    def is_available(self) -> bool:
        """Check if the service is available."""
        self._ensure_initialized()
        return self._client is not None
    
    async def analyze_claim_document(
        self,
        file_data: bytes,
        filename: str
    ) -> Dict[str, Any]:
        """
        Analyze a claim document and extract structured data.
        
        Args:
            file_data: Binary file data
            filename: Name of the file
            
        Returns:
            Dictionary with extracted data and confidence scores
        """
        self._ensure_initialized()
        
        if not self._client:
            raise ValueError("Content Understanding service not available")
        
        # Determine content type from filename
        content_type = "application/pdf"
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            content_type = "image/jpeg"
        elif filename.lower().endswith('.tiff'):
            content_type = "image/tiff"
        
        # Run analysis (synchronous - runs in thread pool)
        result = self._client.analyze_document(
            analyzer_id=settings.azure_content_understanding_analyzer_id,
            file_data=file_data,
            content_type=content_type
        )
        
        # Format response
        return {
            "status": "success",
            "filename": filename,
            "extracted_fields": result.key_value_pairs,
            "confidence_scores": result.confidence_scores,
            "tables": result.tables,
            "content_preview": result.content[:500] if result.content else "",
            "field_count": len(result.key_value_pairs),
            "table_count": len(result.tables),
            "analyzer_id": settings.azure_content_understanding_analyzer_id
        }


# Singleton instance
_service_instance: Optional[ContentUnderstandingService] = None


def get_content_understanding_service() -> ContentUnderstandingService:
    """Get the singleton ContentUnderstandingService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ContentUnderstandingService()
    return _service_instance
