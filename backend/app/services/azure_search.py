"""Azure AI Search service for document indexing and semantic search.

Replaces local FAISS vector store with Azure AI Search for scalable,
cloud-based document indexing and retrieval.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.identity import ClientSecretCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)
from azure.search.documents.models import VectorizedQuery
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.workflow.pdf_processor import get_pdf_processor
from langchain_openai import AzureOpenAIEmbeddings

from app.core.config import get_settings
from app.workflow.pdf_processor import get_pdf_processor

logger = logging.getLogger(__name__)


class AzureSearchService:
    """Service for managing document indexing with Azure AI Search."""
    
    def __init__(self):
        """Initialize Azure AI Search clients with Service Principal authentication."""
        settings = get_settings()
        
        if not settings.azure_search_endpoint:
            raise ValueError("AZURE_SEARCH_ENDPOINT environment variable is required")
        if not settings.azure_tenant_id or not settings.azure_client_id or not settings.azure_client_secret:
            raise ValueError(
                "Service Principal credentials required: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET"
            )
        
        self.endpoint = settings.azure_search_endpoint
        self.index_name = settings.azure_search_index_name or "insurance-policies"
        
        # Create Service Principal credential
        self.credential = ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret
        )
        
        # Initialize clients with Service Principal authentication
        self.index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=self.credential
        )
        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=self.credential
        )
        
        # Initialize embeddings
        self.embeddings = AzureOpenAIEmbeddings(
            model=settings.azure_openai_embedding_model or "text-embedding-3-large",
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version or "2024-08-01-preview",
        )
        
        # Ensure index exists
        self._ensure_index_exists()
    
    def _ensure_index_exists(self):
        """Create the search index if it doesn't exist."""
        try:
            # Check if index exists
            self.index_client.get_index(self.index_name)
            logger.info(f"Search index already exists: {self.index_name}")
        except Exception:
            # Create index
            logger.info(f"Creating search index: {self.index_name}")
            self._create_index()
    
    def _create_index(self):
        """Create a new Azure AI Search index with vector search capabilities."""
        # Define index fields
        fields = [
            SearchField(
                name="id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
            ),
            SearchField(
                name="content",
                type=SearchFieldDataType.String,
                searchable=True,
            ),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=3072,  # text-embedding-3-large dimensions
                vector_search_profile_name="myHnswProfile",
            ),
            SearchField(
                name="source",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SearchField(
                name="policy_type",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SearchField(
                name="section",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SearchField(
                name="file_type",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SearchField(
                name="blob_name",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SearchField(
                name="page_number",
                type=SearchFieldDataType.Int32,
                filterable=True,
            ),
        ]
        
        # Configure vector search
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="myHnsw",
                    parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine"
                    }
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="myHnswProfile",
                    algorithm_configuration_name="myHnsw",
                )
            ],
        )
        
        # Configure semantic search
        semantic_config = SemanticConfiguration(
            name="my-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                content_fields=[SemanticField(field_name="content")],
                keywords_fields=[
                    SemanticField(field_name="policy_type"),
                    SemanticField(field_name="section")
                ]
            )
        )
        
        semantic_search = SemanticSearch(
            configurations=[semantic_config]
        )
        
        # Create index
        index = SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search,
        )
        
        self.index_client.create_index(index)
        logger.info(f"Created search index: {self.index_name}")
    
    def add_documents(
        self,
        documents: List[Document],
        blob_name: Optional[str] = None
    ) -> int:
        """Add documents to the search index.
        
        Args:
            documents: List of LangChain Document objects
            blob_name: Optional blob name to associate with documents
            
        Returns:
            Number of documents successfully indexed
        """
        try:
            # Split documents into chunks
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
            )
            chunks = splitter.split_documents(documents)
            
            # Prepare documents for indexing
            search_documents = []
            for i, chunk in enumerate(chunks):
                # Extract metadata
                source_path = Path(chunk.metadata.get("source", "Unknown"))
                filename = source_path.stem
                file_extension = source_path.suffix.lower()
                
                policy_type = chunk.metadata.get("policy_type", filename.replace("_", " ").title())
                section = chunk.metadata.get("section", "General")
                page_number = chunk.metadata.get("page", None)
                
                # Generate embedding
                content_vector = self.embeddings.embed_query(chunk.page_content)
                
                # Create search document with sanitized ID
                # Azure Search doc IDs can only contain letters, digits, underscore, dash, or equals
                base_id = blob_name or filename
                # Replace invalid characters with underscores
                safe_id = base_id.replace("/", "_").replace(".", "_").replace(" ", "_")
                doc_id = f"{safe_id}_{i}"
                
                search_doc = {
                    "id": doc_id,
                    "content": chunk.page_content,
                    "content_vector": content_vector,
                    "source": str(source_path),
                    "policy_type": policy_type,
                    "section": section,
                    "file_type": file_extension[1:] if file_extension else "unknown",
                    "blob_name": blob_name or "",
                    "page_number": page_number,
                }
                search_documents.append(search_doc)
            
            # Upload to search index in batches
            batch_size = 100
            indexed_count = 0
            
            for i in range(0, len(search_documents), batch_size):
                batch = search_documents[i:i + batch_size]
                result = self.search_client.upload_documents(documents=batch)
                indexed_count += sum(1 for r in result if r.succeeded)
            
            logger.info(f"Successfully indexed {indexed_count} chunks from document")
            return indexed_count
            
        except Exception as e:
            logger.error(f"Failed to add documents to search index: {e}")
            raise
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
        filter_expression: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for documents using vector similarity.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            score_threshold: Minimum similarity score (0-1)
            filter_expression: Optional OData filter expression
            
        Returns:
            List of search results with content and metadata
        """
        try:
            # Generate query embedding
            query_vector = self.embeddings.embed_query(query)
            
            # Create vector query
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top_k,
                fields="content_vector"
            )
            
            # Execute search
            results = self.search_client.search(
                search_text=None,
                vector_queries=[vector_query],
                filter=filter_expression,
                select=["content", "source", "policy_type", "section", "file_type", "blob_name", "page_number"],
                top=top_k
            )
            
            # Format results
            formatted_results = []
            for result in results:
                score = result.get("@search.score", 0)
                
                # Apply score threshold
                if score >= score_threshold:
                    formatted_results.append({
                        "content": result["content"],
                        "metadata": {
                            "source": result.get("source", "Unknown"),
                            "policy_type": result.get("policy_type", "Unknown"),
                            "section": result.get("section", "General"),
                            "file_type": result.get("file_type", "unknown"),
                            "blob_name": result.get("blob_name", ""),
                            "page": result.get("page_number"),
                        },
                        "similarity_score": score,
                        "policy_type": result.get("policy_type", "Unknown"),
                        "section": result.get("section", "General"),
                        "source": result.get("source", "Unknown"),
                    })
            
            logger.info(f"{len(formatted_results)} relevant sections for '{query}'")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    def delete_documents_by_blob(self, blob_name: str) -> int:
        """Delete all documents associated with a specific blob.
        
        Args:
            blob_name: Blob name to filter by
            
        Returns:
            Number of documents deleted
        """
        try:
            # Search for documents with this blob_name
            results = self.search_client.search(
                search_text="*",
                filter=f"blob_name eq '{blob_name}'",
                select=["id"],
                top=1000
            )
            
            # Delete documents
            doc_ids = [{"id": result["id"]} for result in results]
            
            if doc_ids:
                result = self.search_client.delete_documents(documents=doc_ids)
                deleted_count = sum(1 for r in result if r.succeeded)
                logger.info(f"Deleted {deleted_count} chunks for blob: {blob_name}")
                return deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to delete documents for blob {blob_name}: {e}")
            raise
    
    async def add_documents_from_text(
        self,
        text_content: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Add text content to search index.
        
        Args:
            text_content: Text content to index
            source: Source identifier (filename, URL, etc.)
            metadata: Additional metadata
            
        Returns:
            Number of chunks indexed
        """
        # Create a LangChain document
        doc = Document(
            page_content=text_content,
            metadata={
                "source": source,
                **(metadata or {})
            }
        )
        
        return self.add_documents([doc], blob_name=metadata.get("blob_name") if metadata else None)
    
    async def add_documents_from_pdf(
        self,
        pdf_content: bytes,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Process PDF with Document Intelligence and add to search index.
        
        Args:
            pdf_content: PDF file content as bytes
            source: Source identifier
            metadata: Additional metadata
            
        Returns:
            Number of chunks indexed
        """
        try:
            # Use PDF processor to convert to LangChain documents
            pdf_processor = get_pdf_processor()
            
            # Save temporarily to process
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(pdf_content)
                tmp_path = Path(tmp_file.name)
            
            try:
                # Validate PDF
                if not pdf_processor.is_valid_pdf(tmp_path):
                    raise ValueError(f"Invalid PDF file: {source}")
                
                # Convert to documents
                docs = pdf_processor.pdf_to_langchain_documents(tmp_path, chunk_pages=False)
                
                # Add metadata
                for doc in docs:
                    if metadata:
                        doc.metadata.update(metadata)
                    doc.metadata["source"] = source
                
                # Index documents
                return self.add_documents(docs, blob_name=metadata.get("blob_name") if metadata else None)
                
            finally:
                # Clean up temp file
                tmp_path.unlink(missing_ok=True)
                
        except Exception as e:
            logger.error(f"Failed to process PDF {source}: {e}")
            raise
    
    def get_index_statistics(self) -> Dict[str, Any]:
        """Get statistics about the search index.
        
        Returns:
            Dictionary with index statistics
        """
        try:
            # Check if index exists first
            try:
                self.index_client.get_index(self.index_name)
            except Exception as index_err:
                logger.warning(f"Index '{self.index_name}' does not exist yet: {index_err}")
                return {
                    "document_count": 0,
                    "index_name": self.index_name,
                    "index_exists": False
                }
            
            # Get document count
            stats = self.search_client.get_document_count()
            return {
                "document_count": stats,
                "index_name": self.index_name,
                "index_exists": True
            }
        except Exception as e:
            logger.error(f"Failed to get index statistics: {e}")
            return {
                "document_count": 0,
                "index_name": self.index_name,
                "index_exists": False,
                "error": str(e)
            }


# Singleton instance
_azure_search_service: Optional[AzureSearchService] = None


def get_azure_search_service() -> AzureSearchService:
    """Get the Azure AI Search service singleton instance.
    
    Returns:
        AzureSearchService instance
    """
    global _azure_search_service
    if _azure_search_service is None:
        _azure_search_service = AzureSearchService()
    return _azure_search_service
