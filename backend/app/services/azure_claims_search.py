"""Azure AI Search service for claims document indexing and search.

Specialized search service for insurance claim documents with fields
for claim IDs, policy numbers, dates, and extracted Content Understanding data.
"""
from __future__ import annotations

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

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
from langchain_openai import AzureOpenAIEmbeddings

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AzureClaimsSearchService:
    """Service for managing claims document indexing with Azure AI Search."""
    
    def __init__(self):
        """Initialize Azure AI Search clients for claims index."""
        settings = get_settings()
        
        if not settings.azure_search_endpoint:
            raise ValueError("AZURE_SEARCH_ENDPOINT environment variable is required")
        if not settings.azure_tenant_id or not settings.azure_client_id or not settings.azure_client_secret:
            raise ValueError(
                "Service Principal credentials required: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET"
            )
        
        self.endpoint = settings.azure_search_endpoint
        self.index_name = settings.azure_search_claim_index_name or "insurance-claims"
        
        # Create Service Principal credential
        self.credential = ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret
        )
        
        # Initialize clients
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
        """Create the claims search index if it doesn't exist."""
        try:
            self.index_client.get_index(self.index_name)
            logger.info(f"Claims search index already exists: {self.index_name}")
        except Exception:
            logger.info(f"Creating claims search index: {self.index_name}")
            self._create_index()
    
    def _create_index(self):
        """Create a new Azure AI Search index for claims matching Content Understanding schema."""
        # Define index fields - matching Content Understanding output exactly
        fields = [
            # Core document fields
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
                vector_search_dimensions=3072,  # text-embedding-3-large
                vector_search_profile_name="myHnswProfile",
            ),
            SearchField(
                name="blob_name",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SearchField(
                name="source",
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
                name="category",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SearchField(
                name="uploaded_date",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
                sortable=True,
            ),
            
            # Policyholder Information (from Content Understanding)
            SearchField(
                name="policyholder_first_name",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                sortable=True,
            ),
            SearchField(
                name="policyholder_last_name",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                sortable=True,
            ),
            SearchField(
                name="telephone_number",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SearchField(
                name="policyholder_signature",
                type=SearchFieldDataType.String,
                searchable=True,
            ),
            
            # Policy Information
            SearchField(
                name="policy_number",
                type=SearchFieldDataType.String,
                filterable=True,
                sortable=True,
                facetable=True,
            ),
            SearchField(
                name="coverage_type",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SearchField(
                name="policy_effective_date",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
                sortable=True,
            ),
            SearchField(
                name="policy_expiration_date",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
                sortable=True,
            ),
            SearchField(
                name="damage_deductible",
                type=SearchFieldDataType.Double,
                filterable=True,
                sortable=True,
                facetable=True,
            ),
            
            # Claim Information
            SearchField(
                name="claim_number",
                type=SearchFieldDataType.String,
                filterable=True,
                sortable=True,
                facetable=True,
            ),
            SearchField(
                name="date_of_loss",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
                sortable=True,
            ),
            SearchField(
                name="time_of_loss",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SearchField(
                name="date_prepared",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
                sortable=True,
            ),
            SearchField(
                name="signature_date",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
                sortable=True,
            ),
            
            # Location Information
            SearchField(
                name="property_address",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
            ),
            SearchField(
                name="mailing_address",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
            ),
            
            # Loss Details (searchable for semantic queries)
            SearchField(
                name="cause_of_loss",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                facetable=True,
            ),
            SearchField(
                name="loss_description",
                type=SearchFieldDataType.String,
                searchable=True,
            ),
            SearchField(
                name="claim_disclaimer_text",
                type=SearchFieldDataType.String,
                searchable=True,
            ),
            
            # Damaged Items (complex array stored as JSON)
            SearchField(
                name="damaged_items",
                type=SearchFieldDataType.String,
                searchable=False,
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
        
        # Configure semantic search for claims
        semantic_config = SemanticConfiguration(
            name="claims-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                content_fields=[
                    SemanticField(field_name="content"),
                    SemanticField(field_name="loss_description"),
                    SemanticField(field_name="cause_of_loss")
                ],
                keywords_fields=[
                    SemanticField(field_name="claim_number"),
                    SemanticField(field_name="policy_number"),
                    SemanticField(field_name="coverage_type")
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
        logger.info(f"Created claims search index: {self.index_name}")
    
    def add_claim_document(
        self,
        content: str,
        blob_name: str,
        extracted_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Add a claim document to the search index.
        
        Args:
            content: Document text content
            blob_name: Azure Blob Storage path
            extracted_data: Content Understanding extracted fields
            metadata: Additional document metadata
            
        Returns:
            Number of chunks successfully indexed
        """
        try:
            metadata = metadata or {}
            extracted_data = extracted_data or {}
            
            # Split document into chunks
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
            )
            
            # Create LangChain document
            doc = Document(page_content=content, metadata=metadata)
            chunks = splitter.split_documents([doc])
            
            # Helper function to parse date strings from Content Understanding
            def parse_date(date_str: Optional[str]) -> Optional[str]:
                """Convert YYYY-MM-DD date string to ISO 8601 with UTC timezone."""
                if not date_str:
                    return None
                try:
                    if isinstance(date_str, str):
                        # Content Understanding returns dates as YYYY-MM-DD
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                        return dt.isoformat() + "Z"
                    elif isinstance(date_str, datetime):
                        return date_str.isoformat() + "Z"
                except Exception as e:
                    logger.warning(f"Could not parse date '{date_str}': {e}")
                    return None
            
            # Helper function to parse numeric values
            def parse_number(value: Optional[Any]) -> Optional[float]:
                """Convert string or int to float."""
                if value is None:
                    return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
            
            # Extract Content Understanding fields directly (exact field name match)
            claim_number = extracted_data.get("claim_number")
            policy_number = extracted_data.get("policy_number")
            
            # Policyholder information
            policyholder_first_name = extracted_data.get("policyholder_first_name")
            policyholder_last_name = extracted_data.get("policyholder_last_name")
            telephone_number = extracted_data.get("telephone_number")
            policyholder_signature = extracted_data.get("policyholder_signature")
            
            # Policy information
            coverage_type = extracted_data.get("coverage_type")
            policy_effective_date = parse_date(extracted_data.get("policy_effective_date"))
            policy_expiration_date = parse_date(extracted_data.get("policy_expiration_date"))
            damage_deductible = parse_number(extracted_data.get("damage_deductible"))
            
            # Claim information
            date_of_loss = parse_date(extracted_data.get("date_of_loss"))
            time_of_loss = extracted_data.get("time_of_loss")
            date_prepared = parse_date(extracted_data.get("date_prepared"))
            signature_date = parse_date(extracted_data.get("signature_date"))
            
            # Location information
            property_address = extracted_data.get("property_address")
            mailing_address = extracted_data.get("mailing_address")
            
            # Loss details
            cause_of_loss = extracted_data.get("cause_of_loss")
            loss_description = extracted_data.get("loss_description")
            claim_disclaimer_text = extracted_data.get("claim_disclaimer_text")
            
            # Damaged items (complex array stored as JSON)
            damaged_items = extracted_data.get("damaged_items")
            damaged_items_json = json.dumps(damaged_items) if damaged_items else None
            
            # Prepare documents for indexing
            search_documents = []
            uploaded_date = datetime.utcnow().isoformat() + "Z"
            
            for i, chunk in enumerate(chunks):
                # Generate embedding
                content_vector = self.embeddings.embed_query(chunk.page_content)
                
                # Create search document with sanitized ID
                safe_id = blob_name.replace("/", "_").replace(".", "_").replace(" ", "_")
                doc_id = f"{safe_id}_{i}"
                
                search_doc = {
                    # Core fields
                    "id": doc_id,
                    "content": chunk.page_content,
                    "content_vector": content_vector,
                    "blob_name": blob_name,
                    "source": metadata.get("source", blob_name),
                    "file_type": metadata.get("file_type", "pdf"),
                    "category": "claim",
                    "uploaded_date": uploaded_date,
                    
                    # Policyholder information (from CU)
                    "policyholder_first_name": policyholder_first_name,
                    "policyholder_last_name": policyholder_last_name,
                    "telephone_number": telephone_number,
                    "policyholder_signature": policyholder_signature,
                    
                    # Policy information (from CU)
                    "policy_number": policy_number,
                    "coverage_type": coverage_type,
                    "policy_effective_date": policy_effective_date,
                    "policy_expiration_date": policy_expiration_date,
                    "damage_deductible": damage_deductible,
                    
                    # Claim information (from CU)
                    "claim_number": claim_number,
                    "date_of_loss": date_of_loss,
                    "time_of_loss": time_of_loss,
                    "date_prepared": date_prepared,
                    "signature_date": signature_date,
                    
                    # Location information (from CU)
                    "property_address": property_address,
                    "mailing_address": mailing_address,
                    
                    # Loss details (from CU)
                    "cause_of_loss": cause_of_loss,
                    "loss_description": loss_description,
                    "claim_disclaimer_text": claim_disclaimer_text,
                    
                    # Complex array (from CU)
                    "damaged_items": damaged_items_json,
                }
                search_documents.append(search_doc)
            
            # Upload to search index in batches
            batch_size = 100
            indexed_count = 0
            
            for i in range(0, len(search_documents), batch_size):
                batch = search_documents[i:i + batch_size]
                result = self.search_client.upload_documents(documents=batch)
                indexed_count += sum(1 for r in result if r.succeeded)
            
            logger.info(f"Successfully indexed {indexed_count} claim chunks (claim_number: {claim_number})")
            return indexed_count
            
        except Exception as e:
            logger.error(f"Failed to add claim document to search index: {e}")
            raise
    
    def search_by_claim_number(
        self,
        claim_number: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for all documents related to a specific claim number.
        
        Args:
            claim_number: The claim number to search for
            top_k: Maximum number of results
            
        Returns:
            List of search results with CU fields
        """
        try:
            filter_expr = f"claim_number eq '{claim_number}'"
            
            results = self.search_client.search(
                search_text="*",
                filter=filter_expr,
                select=["content", "claim_number", "policy_number", "policyholder_first_name", 
                       "policyholder_last_name", "date_of_loss", "cause_of_loss", "loss_description",
                       "coverage_type", "damage_deductible", "uploaded_date", "damaged_items"],
                top=top_k
            )
            
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"Claim number search failed: {e}")
            raise
    
    def search_by_policy_number(
        self,
        policy_number: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for all claims related to a specific policy number."""
        try:
            filter_expr = f"policy_number eq '{policy_number}'"
            
            results = self.search_client.search(
                search_text="*",
                filter=filter_expr,
                select=["content", "claim_number", "policy_number", "policyholder_first_name",
                       "policyholder_last_name", "date_of_loss", "coverage_type", "uploaded_date"],
                top=top_k
            )
            
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"Policy number search failed: {e}")
            raise
    
    def search_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        top_k: int = 50
    ) -> List[Dict[str, Any]]:
        """Search for claims within a date range (by date_of_loss)."""
        try:
            start_str = start_date.isoformat() + "Z"
            end_str = end_date.isoformat() + "Z"
            filter_expr = f"date_of_loss ge {start_str} and date_of_loss le {end_str}"
            
            results = self.search_client.search(
                search_text="*",
                filter=filter_expr,
                select=["content", "claim_number", "policy_number", "policyholder_first_name",
                       "policyholder_last_name", "date_of_loss", "cause_of_loss"],
                top=top_k,
                order_by=["date_of_loss desc"]
            )
            
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"Date range search failed: {e}")
            raise
    
    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        filter_expression: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search claims using vector similarity.
        
        Args:
            query: Search query text
            top_k: Number of results to return
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
                select=["content", "claim_id", "policy_number", "claimant_name",
                       "incident_date", "document_type", "extracted_fields"],
                top=top_k
            )
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "content": result.get("content", ""),
                    "claim_id": result.get("claim_id"),
                    "policy_number": result.get("policy_number"),
                    "claimant_name": result.get("claimant_name"),
                    "incident_date": result.get("incident_date"),
                    "document_type": result.get("document_type"),
                    "extracted_fields": json.loads(result.get("extracted_fields", "{}")),
                    "score": result.get("@search.score", 0)
                })
            
            logger.info(f"Found {len(formatted_results)} relevant claims for query: {query}")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise
    
    def delete_documents_by_blob(self, blob_name: str) -> int:
        """Delete all documents associated with a specific blob."""
        try:
            filter_expr = f"blob_name eq '{blob_name}'"
            
            # Find documents to delete
            results = self.search_client.search(
                search_text="*",
                filter=filter_expr,
                select=["id"],
                top=1000
            )
            
            doc_ids = [{"id": result["id"]} for result in results]
            
            if doc_ids:
                result = self.search_client.delete_documents(documents=doc_ids)
                deleted_count = sum(1 for r in result if r.succeeded)
                logger.info(f"Deleted {deleted_count} claim chunks for blob: {blob_name}")
                return deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to delete claim documents: {e}")
            raise
    
    def get_index_statistics(self) -> Dict[str, Any]:
        """Get statistics about the claims index."""
        try:
            index = self.index_client.get_index(self.index_name)
            stats = self.index_client.get_index_statistics(self.index_name)
            
            # Stats can be either an object or a dict depending on SDK version
            if isinstance(stats, dict):
                return {
                    "index_name": self.index_name,
                    "document_count": stats.get("document_count", 0),
                    "storage_size": stats.get("storage_size", 0),
                    "vector_index_size": stats.get("vector_index_size"),
                }
            else:
                return {
                    "index_name": self.index_name,
                    "document_count": stats.document_count,
                    "storage_size": stats.storage_size,
                    "vector_index_size": getattr(stats, 'vector_index_size', None),
                }
        except Exception as e:
            logger.error(f"Failed to get index statistics: {e}", exc_info=True)
            return {
                "index_name": self.index_name,
                "document_count": 0,
                "storage_size": 0,
            }


# Singleton instance
_claims_search_service: Optional[AzureClaimsSearchService] = None


def get_azure_claims_search_service() -> AzureClaimsSearchService:
    """Get or create the Azure Claims Search Service singleton."""
    global _claims_search_service
    if _claims_search_service is None:
        _claims_search_service = AzureClaimsSearchService()
    return _claims_search_service
