"""Cosmos DB service for agent persistence and tracking.

This service manages storage and retrieval of:
- Agent definitions (with versioning)
- Agent execution history (workflow traces)
- Token usage records (OpenTelemetry data)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.cosmos.container import ContainerProxy
from azure.identity import DefaultAzureCredential

from app.core.config import get_settings
from app.models.agent_models import (
    AgentDefinition,
    AgentExecution,
    AgentType,
    AgentVersion,
    ExecutionStatus,
    TokenUsageRecord,
)

logger = logging.getLogger(__name__)


class CosmosAgentService:
    """Service for managing agent data in Cosmos DB."""
    
    def __init__(self):
        """Initialize Cosmos DB client and containers."""
        self.settings = get_settings()
        self.client: Optional[CosmosClient] = None
        self._definitions_container: Optional[ContainerProxy] = None
        self._executions_container: Optional[ContainerProxy] = None
        self._token_usage_container: Optional[ContainerProxy] = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize Cosmos DB connection and containers.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True
        
        try:
            if not self.settings.azure_cosmos_endpoint:
                logger.warning("Cosmos DB endpoint not configured. Agent persistence disabled.")
                return False
            
            # Use Service Principal authentication
            credential = DefaultAzureCredential()
            
            # Create Cosmos client
            self.client = CosmosClient(
                url=self.settings.azure_cosmos_endpoint,
                credential=credential
            )
            
            # Get or create database
            database = self.client.create_database_if_not_exists(
                id=self.settings.azure_cosmos_database_name
            )
            logger.info(f"✅ Connected to Cosmos DB database: {self.settings.azure_cosmos_database_name}")
            
            # Create containers with partition keys
            self._definitions_container = database.create_container_if_not_exists(
                id=self.settings.azure_cosmos_agent_definitions_container,
                partition_key=PartitionKey(path="/id"),
                offer_throughput=400
            )
            logger.info(f"✅ Agent definitions container ready: {self.settings.azure_cosmos_agent_definitions_container}")
            
            self._executions_container = database.create_container_if_not_exists(
                id=self.settings.azure_cosmos_agent_executions_container,
                partition_key=PartitionKey(path="/id"),
                offer_throughput=400
            )
            logger.info(f"✅ Agent executions container ready: {self.settings.azure_cosmos_agent_executions_container}")
            
            self._token_usage_container = database.create_container_if_not_exists(
                id=self.settings.azure_cosmos_token_usage_container,
                partition_key=PartitionKey(path="/record_id"),
                offer_throughput=400
            )
            logger.info(f"✅ Token usage container ready: {self.settings.azure_cosmos_token_usage_container}")
            
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Cosmos DB: {e}")
            return False
    
    # ==================== AGENT DEFINITIONS ====================
    
    async def save_agent_definition(self, agent_def: AgentDefinition) -> AgentDefinition:
        """Save or update an agent definition.
        
        Args:
            agent_def: Agent definition to save
            
        Returns:
            Saved agent definition with updated timestamp
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._definitions_container:
            logger.warning("Definitions container not available")
            return agent_def
        
        try:
            agent_def.updated_at = datetime.utcnow()
            
            # Convert to dict for Cosmos DB
            agent_dict = agent_def.model_dump(mode='json')
            
            # Upsert the document
            result = self._definitions_container.upsert_item(agent_dict)
            
            logger.info(f"✅ Saved agent definition: {agent_def.id} v{agent_def.version}")
            return AgentDefinition(**result)
            
        except Exception as e:
            logger.error(f"❌ Failed to save agent definition {agent_def.id}: {e}")
            raise
    
    async def get_agent_definition(self, agent_id: str) -> Optional[AgentDefinition]:
        """Retrieve an agent definition by ID.
        
        Args:
            agent_id: Unique agent identifier
            
        Returns:
            Agent definition if found, None otherwise
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._definitions_container:
            return None
        
        try:
            item = self._definitions_container.read_item(
                item=agent_id,
                partition_key=agent_id
            )
            return AgentDefinition(**item)
            
        except exceptions.CosmosResourceNotFoundError:
            logger.debug(f"Agent definition not found: {agent_id}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get agent definition {agent_id}: {e}")
            return None
    
    async def list_agent_definitions(
        self,
        agent_type: Optional[AgentType] = None,
        is_active: Optional[bool] = None
    ) -> List[AgentDefinition]:
        """List agent definitions with optional filters.
        
        Args:
            agent_type: Filter by agent type
            is_active: Filter by active status
            
        Returns:
            List of agent definitions
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._definitions_container:
            return []
        
        try:
            query = "SELECT * FROM c WHERE 1=1"
            parameters = []
            
            if agent_type:
                query += " AND c.agent_type = @agent_type"
                parameters.append({"name": "@agent_type", "value": agent_type.value})
            
            if is_active is not None:
                query += " AND c.is_active = @is_active"
                parameters.append({"name": "@is_active", "value": is_active})
            
            query += " ORDER BY c.updated_at DESC"
            
            items = list(self._definitions_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            return [AgentDefinition(**item) for item in items]
            
        except Exception as e:
            logger.error(f"❌ Failed to list agent definitions: {e}")
            return []
    
    async def create_new_version(
        self,
        agent_id: str,
        new_version: str,
        changelog: str,
        updated_by: str = "system"
    ) -> Optional[AgentDefinition]:
        """Create a new version of an agent definition.
        
        Args:
            agent_id: Agent to version
            new_version: New semantic version
            changelog: Description of changes
            updated_by: Who made the change
            
        Returns:
            Updated agent definition with new version
        """
        agent_def = await self.get_agent_definition(agent_id)
        if not agent_def:
            return None
        
        # Add current version to history
        version_record = AgentVersion(
            version=agent_def.version,
            created_at=agent_def.updated_at,
            created_by=updated_by,
            changelog=changelog
        )
        agent_def.version_history.append(version_record)
        
        # Update to new version
        agent_def.version = new_version
        
        return await self.save_agent_definition(agent_def)
    
    # ==================== AGENT EXECUTIONS ====================
    
    async def save_execution(self, execution: AgentExecution) -> AgentExecution:
        """Save or update an agent execution record.
        
        Args:
            execution: Execution record to save
            
        Returns:
            Saved execution record
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._executions_container:
            logger.warning("Executions container not available")
            return execution
        
        try:
            # Convert to dict for Cosmos DB
            execution_dict = execution.model_dump(mode='json')
            
            # Upsert the document
            result = self._executions_container.upsert_item(execution_dict)
            
            logger.debug(f"✅ Saved execution: {execution.id} for claim {execution.claim_id}")
            return AgentExecution(**result)
            
        except Exception as e:
            logger.error(f"❌ Failed to save execution {execution.id}: {e}")
            raise
    
    async def save_token_usage(self, token_record: 'TokenUsageRecord') -> 'TokenUsageRecord':
        """Save a token usage record to Cosmos DB.
        
        Args:
            token_record: Token usage record to save
            
        Returns:
            Saved token record
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._token_usage_container:
            logger.warning("Token usage container not available")
            return token_record
        
        try:
            from app.models.agent_models import TokenUsageRecord
            
            # Convert to dict for Cosmos DB
            record_dict = token_record.model_dump(mode='json')
            
            # Ensure proper datetime serialization
            if 'timestamp' in record_dict and hasattr(record_dict['timestamp'], 'isoformat'):
                record_dict['timestamp'] = record_dict['timestamp'].isoformat()
            
            # Upsert the document
            result = await self._token_usage_container.upsert_item(token_record_dict)
            
            logger.debug(f"✅ Saved token usage: {token_record.record_id} ({token_record.total_tokens} tokens, ${token_record.total_cost:.6f})")
            return TokenUsageRecord(**result)
            
        except Exception as e:
            logger.error(f"❌ Failed to save token usage {token_record.record_id}: {e}")
            return token_record
    
    async def get_execution(self, execution_id: str) -> Optional[AgentExecution]:
        """Retrieve an execution record by ID.
        
        Args:
            execution_id: Unique execution identifier
            
        Returns:
            Execution record if found, None otherwise
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._executions_container:
            return None
        
        try:
            item = self._executions_container.read_item(
                item=execution_id,
                partition_key=execution_id
            )
            return AgentExecution(**item)
            
        except exceptions.CosmosResourceNotFoundError:
            logger.debug(f"Execution not found: {execution_id}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get execution {execution_id}: {e}")
            return None
    
    async def list_executions(
        self,
        claim_id: Optional[str] = None,
        status: Optional[ExecutionStatus] = None,
        limit: int = 100
    ) -> List[AgentExecution]:
        """List execution records with optional filters.
        
        Args:
            claim_id: Filter by claim ID
            status: Filter by execution status
            limit: Maximum number of records to return
            
        Returns:
            List of execution records
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._executions_container:
            return []
        
        try:
            query = "SELECT * FROM c WHERE 1=1"
            parameters = []
            
            if claim_id:
                query += " AND c.claim_id = @claim_id"
                parameters.append({"name": "@claim_id", "value": claim_id})
            
            if status:
                query += " AND c.status = @status"
                parameters.append({"name": "@status", "value": status.value})
            
            query += f" ORDER BY c.started_at DESC OFFSET 0 LIMIT {limit}"
            
            items = list(self._executions_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            return [AgentExecution(**item) for item in items]
            
        except Exception as e:
            logger.error(f"❌ Failed to list executions: {e}")
            return []
    
    async def get_claim_execution_history(self, claim_id: str) -> List[AgentExecution]:
        """Get all execution records for a specific claim.
        
        Args:
            claim_id: Claim identifier
            
        Returns:
            List of executions for the claim, ordered by time
        """
        return await self.list_executions(claim_id=claim_id)
    
    # ==================== TOKEN USAGE ====================
    
    async def save_token_usage(self, record: TokenUsageRecord) -> TokenUsageRecord:
        """Save a token usage record.
        
        Args:
            record: Token usage record to save
            
        Returns:
            Saved token usage record
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._token_usage_container:
            logger.warning("Token usage container not available")
            return record
        
        try:
            # Convert to dict for Cosmos DB
            record_dict = record.model_dump(mode='json')
            
            # Upsert the document
            result = self._token_usage_container.upsert_item(record_dict)
            
            logger.debug(f"✅ Saved token usage: {record.record_id} ({record.total_tokens} tokens)")
            return TokenUsageRecord(**result)
            
        except Exception as e:
            logger.error(f"❌ Failed to save token usage {record.record_id}: {e}")
            # Fail soft - don't propagate error
            return record
    
    async def get_token_usage_by_claim(
        self,
        claim_id: str
    ) -> List[TokenUsageRecord]:
        """Get all token usage records for a claim.
        
        Args:
            claim_id: Claim identifier
            
        Returns:
            List of token usage records
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._token_usage_container:
            return []
        
        try:
            query = "SELECT * FROM c WHERE c.claim_id = @claim_id ORDER BY c.timestamp ASC"
            parameters = [{"name": "@claim_id", "value": claim_id}]
            
            items = list(self._token_usage_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            return [TokenUsageRecord(**item) for item in items]
            
        except Exception as e:
            logger.error(f"❌ Failed to get token usage for claim {claim_id}: {e}")
            return []
    
    async def get_token_usage_by_execution(
        self,
        execution_id: str
    ) -> List[TokenUsageRecord]:
        """Get all token usage records for a workflow execution.
        
        Args:
            execution_id: Workflow execution ID
            
        Returns:
            List of token usage records
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._token_usage_container:
            return []
        
        try:
            query = "SELECT * FROM c WHERE c.execution_id = @execution_id ORDER BY c.timestamp ASC"
            parameters = [{"name": "@execution_id", "value": execution_id}]
            
            items = list(self._token_usage_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            return [TokenUsageRecord(**item) for item in items]
            
        except Exception as e:
            logger.error(f"❌ Failed to get token usage for execution {execution_id}: {e}")
            return []
    
    async def get_token_usage_analytics(
        self,
        agent_type: Optional[AgentType] = None,
        days_back: int = 7
    ) -> Dict[str, Any]:
        """Get aggregated token usage analytics.
        
        Args:
            agent_type: Filter by agent type
            days_back: Number of days to look back
            
        Returns:
            Dictionary with analytics data
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._token_usage_container:
            return {"total_tokens": 0, "total_cost": 0.0, "by_agent": {}}
        
        try:
            from datetime import timedelta
            start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            query = "SELECT * FROM c WHERE c.timestamp >= @start_date"
            parameters = [{"name": "@start_date", "value": start_date.isoformat()}]
            
            if agent_type:
                query += " AND c.agent_type = @agent_type"
                parameters.append({"name": "@agent_type", "value": agent_type.value})
            
            items = list(self._token_usage_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            # Aggregate by agent type
            by_agent = {}
            total_tokens = 0
            total_cost = 0.0
            
            for item in items:
                agent = item.get("agent_type", "unknown")
                if agent not in by_agent:
                    by_agent[agent] = {"tokens": 0, "cost": 0.0, "requests": 0}
                
                by_agent[agent]["tokens"] += item.get("total_tokens", 0)
                by_agent[agent]["cost"] += item.get("total_cost", 0.0)
                by_agent[agent]["requests"] += 1
                
                total_tokens += item.get("total_tokens", 0)
                total_cost += item.get("total_cost", 0.0)
            
            return {
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 4),
                "by_agent": by_agent,
                "period_days": days_back,
                "total_requests": len(items)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get token usage analytics: {e}")
            return {"total_tokens": 0, "total_cost": 0.0, "by_agent": {}}


# Global singleton instance
_cosmos_service: Optional[CosmosAgentService] = None


async def get_cosmos_service() -> CosmosAgentService:
    """Get or create the global Cosmos DB service instance.
    
    Returns:
        Initialized Cosmos DB service
    """
    global _cosmos_service
    if _cosmos_service is None:
        _cosmos_service = CosmosAgentService()
        await _cosmos_service.initialize()
    return _cosmos_service
