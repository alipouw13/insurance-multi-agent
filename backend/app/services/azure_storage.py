"""Azure Blob Storage service for document management.

Handles uploading, downloading, and managing insurance policy documents
in Azure Blob Storage instead of local filesystem.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO, Optional

from azure.storage.blob import (
    BlobServiceClient,
    BlobClient,
    ContainerClient,
    generate_blob_sas,
    BlobSasPermissions,
    ContentSettings
)
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity import ClientSecretCredential

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AzureStorageService:
    """Service for managing documents in Azure Blob Storage."""
    
    def __init__(self):
        """Initialize Azure Blob Storage client with Service Principal authentication."""
        settings = get_settings()
        
        # Validate required settings
        if not settings.azure_storage_account_name:
            raise ValueError("AZURE_STORAGE_ACCOUNT_NAME environment variable is required")
        if not settings.azure_tenant_id or not settings.azure_client_id or not settings.azure_client_secret:
            raise ValueError(
                "Service Principal credentials required: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET"
            )
        
        self.account_name = settings.azure_storage_account_name
        self.container_name = settings.azure_storage_container_name or "insurance-documents"
        self.account_url = f"https://{self.account_name}.blob.core.windows.net"
        
        # Create Service Principal credential
        self.credential = ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret
        )
        
        # Initialize clients with Service Principal authentication
        self.blob_service_client = BlobServiceClient(
            account_url=self.account_url,
            credential=self.credential
        )
        self.container_client = self.blob_service_client.get_container_client(
            self.container_name
        )
        
        # Ensure container exists
        self._ensure_container_exists()
    
    def _ensure_container_exists(self):
        """Create the container if it doesn't exist."""
        try:
            self.container_client.create_container()
            logger.info(f"Created blob container: {self.container_name}")
        except ResourceExistsError:
            logger.debug(f"Blob container already exists: {self.container_name}")
        except Exception as e:
            logger.error(f"Failed to create/access container: {e}")
            raise
    
    def upload_document(
        self,
        file_data: BinaryIO,
        filename: str,
        category: str = "policy",
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> tuple[str, str]:
        """Upload a document to Azure Blob Storage.
        
        Args:
            file_data: File-like object containing the document data
            filename: Original filename
            category: Document category (policy, regulation, reference)
            content_type: MIME type of the document
            metadata: Additional metadata to store with the blob
            
        Returns:
            Tuple of (blob_name, blob_url)
        """
        # Generate unique blob name
        doc_id = str(uuid.uuid4())
        file_extension = Path(filename).suffix
        blob_name = f"{category}/{doc_id}{file_extension}"
        
        # Prepare metadata
        blob_metadata = {
            "original_filename": filename,
            "category": category,
            "upload_date": datetime.utcnow().isoformat(),
            "doc_id": doc_id
        }
        if metadata:
            blob_metadata.update(metadata)
        
        # Set content settings
        content_settings = ContentSettings(
            content_type=content_type,
            content_disposition=f'inline; filename="{filename}"'
        )
        
        try:
            # Upload blob
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.upload_blob(
                file_data,
                overwrite=True,
                content_settings=content_settings,
                metadata=blob_metadata
            )
            
            blob_url = blob_client.url
            logger.info(f"Uploaded document to blob storage: {blob_name}")
            
            return blob_name, blob_url
            
        except Exception as e:
            logger.error(f"Failed to upload document {filename}: {e}")
            raise
    
    def download_document(self, blob_name: str) -> bytes:
        """Download a document from Azure Blob Storage.
        
        Args:
            blob_name: Name of the blob to download
            
        Returns:
            Document content as bytes
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            return blob_client.download_blob().readall()
        except ResourceNotFoundError:
            logger.error(f"Blob not found: {blob_name}")
            raise
        except Exception as e:
            logger.error(f"Failed to download blob {blob_name}: {e}")
            raise
    
    def delete_document(self, blob_name: str) -> bool:
        """Delete a document from Azure Blob Storage.
        
        Args:
            blob_name: Name of the blob to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.delete_blob()
            logger.info(f"Deleted blob: {blob_name}")
            return True
        except ResourceNotFoundError:
            logger.warning(f"Blob not found for deletion: {blob_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete blob {blob_name}: {e}")
            return False
    
    def get_blob_metadata(self, blob_name: str) -> dict:
        """Get metadata for a blob.
        
        Args:
            blob_name: Name of the blob
            
        Returns:
            Dictionary of blob metadata
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            properties = blob_client.get_blob_properties()
            return properties.metadata
        except Exception as e:
            logger.error(f"Failed to get blob metadata for {blob_name}: {e}")
            raise
    
    def list_documents(self, category: Optional[str] = None) -> list[dict]:
        """List all documents in storage, optionally filtered by category.
        
        Args:
            category: Optional category to filter by
            
        Returns:
            List of blob metadata dictionaries
        """
        try:
            prefix = f"{category}/" if category else None
            blobs = self.container_client.list_blobs(name_starts_with=prefix)
            
            documents = []
            for blob in blobs:
                doc_info = {
                    "blob_name": blob.name,
                    "size": blob.size,
                    "created": blob.creation_time,
                    "modified": blob.last_modified,
                    "content_type": blob.content_settings.content_type if blob.content_settings else None,
                    "metadata": blob.metadata
                }
                documents.append(doc_info)
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise
    
    def generate_sas_url(
        self,
        blob_name: str,
        expiry_hours: int = 1,
        permissions: str = "r"
    ) -> str:
        """Generate a SAS URL for temporary access to a blob.
        
        Note: With Service Principal authentication, we cannot generate SAS tokens.
        Instead, we return the direct blob URL. The caller must use the same
        Service Principal credentials to access the blob.
        
        Args:
            blob_name: Name of the blob
            expiry_hours: Hours until the SAS token expires (ignored with SPN auth)
            permissions: Permissions string (ignored with SPN auth)
            
        Returns:
            Direct blob URL (requires Service Principal authentication to access)
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # With Service Principal auth, we can't generate SAS tokens without the account key
            # Return the direct URL - client must authenticate with the same SPN
            logger.info(f"Returning direct blob URL for {blob_name} (SPN auth mode)")
            return blob_client.url
            
        except Exception as e:
            logger.error(f"Failed to get blob URL for {blob_name}: {e}")
            raise


# Singleton instance
_azure_storage_service: Optional[AzureStorageService] = None


def get_azure_storage_service() -> AzureStorageService:
    """Get the Azure Storage service singleton instance.
    
    Returns:
        AzureStorageService instance
    """
    global _azure_storage_service
    if _azure_storage_service is None:
        _azure_storage_service = AzureStorageService()
    return _azure_storage_service
