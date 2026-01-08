"""Fabric Lakehouse direct SQL query service.

This service provides a fallback mechanism when the Fabric Data Agent fails
due to authentication or connectivity issues. It queries the Lakehouse SQL
analytics endpoint directly using pyodbc with Service Principal authentication.

The Fabric SQL analytics endpoint supports Service Principal authentication,
unlike the Fabric Data Agent which requires user identity passthrough (OBO).

Requirements:
- ODBC Driver 18 for SQL Server installed
- pyodbc package installed
- Service Principal with access to the Fabric Lakehouse
"""
import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Try to import pyodbc - may not be available in all environments
try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False
    logger.warning(
        "[LAKEHOUSE] pyodbc not available. Lakehouse fallback will return demo data. "
        "Install with: pip install pyodbc"
    )


class LakehouseService:
    """Service for querying Fabric Lakehouse SQL analytics endpoint."""
    
    def __init__(
        self, 
        server: str = None,
        database: str = None,
        tenant_id: str = None,
        client_id: str = None,
        client_secret: str = None
    ):
        """Initialize the Lakehouse service.
        
        Args:
            server: SQL analytics endpoint server (e.g., xxx.datawarehouse.fabric.microsoft.com)
            database: Database name (usually the lakehouse name)
            tenant_id: Azure tenant ID
            client_id: Service Principal client ID
            client_secret: Service Principal client secret
        """
        from app.core.config import get_settings
        settings = get_settings()
        
        self.server = server or os.getenv("FABRIC_SQL_SERVER")
        self.database = database or os.getenv("FABRIC_SQL_DATABASE", "insurance_claims_lakehouse")
        self.tenant_id = tenant_id or settings.azure_tenant_id
        self.client_id = client_id or settings.azure_client_id
        self.client_secret = client_secret or settings.azure_client_secret
        
        self._connection = None
        
    def _get_connection_string(self) -> str:
        """Build ODBC connection string for Fabric SQL analytics endpoint."""
        # Service Principal authentication
        return (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={self.server};"
            f"DATABASE={self.database};"
            f"Authentication=ActiveDirectoryServicePrincipal;"
            f"UID={self.client_id}@{self.tenant_id};"
            f"PWD={self.client_secret};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
        )
    
    def _connect(self):
        """Establish connection to the Lakehouse SQL endpoint."""
        if not PYODBC_AVAILABLE:
            raise RuntimeError("pyodbc is not available")
            
        if not all([self.server, self.database, self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError(
                "Missing Lakehouse configuration. Required: FABRIC_SQL_SERVER, FABRIC_SQL_DATABASE, "
                "AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET"
            )
        
        conn_string = self._get_connection_string()
        logger.info(f"[LAKEHOUSE] Connecting to {self.server}/{self.database}")
        self._connection = pyodbc.connect(conn_string)
        return self._connection
    
    def query(self, sql: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results as list of dicts.
        
        Args:
            sql: SQL query string
            params: Optional query parameters
            
        Returns:
            List of dictionaries, one per row
        """
        if not PYODBC_AVAILABLE:
            logger.warning("[LAKEHOUSE] pyodbc not available, returning empty results")
            return []
            
        try:
            conn = self._connect()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            columns = [column[0] for column in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            cursor.close()
            conn.close()
            
            logger.info(f"[LAKEHOUSE] Query returned {len(results)} rows")
            return results
            
        except Exception as e:
            logger.error(f"[LAKEHOUSE] Query failed: {e}")
            raise
    
    def get_claimant_history(self, claimant_id: str) -> List[Dict[str, Any]]:
        """Get claim history for a specific claimant.
        
        Args:
            claimant_id: The claimant ID to look up
            
        Returns:
            List of claim records
        """
        sql = """
        SELECT 
            claim_id, policy_number, claimant_id, claim_type, claim_amount,
            claim_date, incident_date, settlement_date, status,
            location, fraud_flag
        FROM claims_history
        WHERE claimant_id = ?
        ORDER BY claim_date DESC
        """
        return self.query(sql, (claimant_id,))
    
    def get_fraud_rate_by_region(self, state: str, claim_type: str = None) -> Dict[str, Any]:
        """Get fraud statistics for a region.
        
        Args:
            state: State abbreviation
            claim_type: Optional claim type filter
            
        Returns:
            Dict with fraud rate statistics
        """
        if claim_type:
            sql = """
            SELECT 
                state,
                claim_type,
                COUNT(*) as total_claims,
                SUM(CASE WHEN fraud_flag = 1 THEN 1 ELSE 0 END) as fraud_claims,
                AVG(claim_amount) as avg_claim_amount,
                CAST(SUM(CASE WHEN fraud_flag = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as fraud_rate
            FROM claims_history
            WHERE state = ? AND claim_type LIKE ?
            GROUP BY state, claim_type
            """
            results = self.query(sql, (state, f"%{claim_type}%"))
        else:
            sql = """
            SELECT 
                state,
                COUNT(*) as total_claims,
                SUM(CASE WHEN fraud_flag = 1 THEN 1 ELSE 0 END) as fraud_claims,
                AVG(claim_amount) as avg_claim_amount,
                CAST(SUM(CASE WHEN fraud_flag = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as fraud_rate
            FROM claims_history
            WHERE state = ?
            GROUP BY state
            """
            results = self.query(sql, (state,))
        
        return results[0] if results else {}


def get_demo_claims_data(claimant_id: str, claim_type: str, state: str, claimant_name: str) -> str:
    """Generate demo claims data response when Lakehouse/Fabric is unavailable.
    
    This provides realistic-looking data for demonstration purposes when:
    - Fabric Data Agent fails due to authentication issues
    - Lakehouse SQL endpoint is not configured
    - pyodbc is not available
    
    Args:
        claimant_id: Claimant ID
        claim_type: Type of claim
        state: State abbreviation
        claimant_name: Name of claimant
        
    Returns:
        Formatted string with demo analysis data
    """
    import random
    import hashlib
    
    # Use claimant_id to seed random for consistent demo data
    seed = int(hashlib.md5(claimant_id.encode()).hexdigest()[:8], 16)
    random.seed(seed)
    
    # Generate demo history
    total_claims = random.randint(1, 5)
    approved_claims = random.randint(0, total_claims)
    denied_claims = total_claims - approved_claims
    total_amount = sum([random.randint(1000, 25000) for _ in range(total_claims)])
    avg_amount = total_amount // total_claims if total_claims > 0 else 0
    
    # Regional fraud rate based on state (demo values)
    state_fraud_rates = {
        'CA': 4.2, 'FL': 5.8, 'TX': 3.9, 'NY': 4.5, 'IL': 3.7,
        'PA': 3.2, 'OH': 3.0, 'GA': 4.8, 'NC': 3.5, 'MI': 3.8
    }
    fraud_rate = state_fraud_rates.get(state, 3.5)
    
    # Claim type specific rates
    claim_type_lower = claim_type.lower()
    if 'collision' in claim_type_lower:
        type_fraud_rate = fraud_rate + random.uniform(0.5, 1.5)
        type_avg_claim = random.randint(15000, 35000)
    elif 'theft' in claim_type_lower:
        type_fraud_rate = fraud_rate + random.uniform(2.0, 4.0)
        type_avg_claim = random.randint(8000, 20000)
    elif 'fire' in claim_type_lower:
        type_fraud_rate = fraud_rate + random.uniform(1.0, 2.5)
        type_avg_claim = random.randint(25000, 75000)
    else:
        type_fraud_rate = fraud_rate
        type_avg_claim = random.randint(5000, 15000)
    
    # Risk assessment
    risk_score = random.randint(15, 85)
    risk_level = "Low" if risk_score < 30 else "Medium" if risk_score < 60 else "High"
    
    # Generate response
    return f"""## Claims Data Analysis for {claimant_name} ({claimant_id})

### ⚠️ Demo Data Mode
*Note: This analysis uses demonstration data. Fabric Data Agent connection unavailable.*

---

### Claimant History Summary

| Metric | Value |
|--------|-------|
| Total Claims Filed | {total_claims} |
| Approved Claims | {approved_claims} |
| Denied Claims | {denied_claims} |
| Total Amount Claimed | ${total_amount:,} |
| Average Claim Amount | ${avg_amount:,} |
| Account Risk Score | {risk_score}/100 ({risk_level}) |

### Regional Statistics ({state})

| Metric | Value |
|--------|-------|
| Regional Fraud Rate | {fraud_rate:.1f}% |
| {claim_type} Fraud Rate | {type_fraud_rate:.1f}% |
| Average {claim_type} Claim | ${type_avg_claim:,} |

### Risk Indicators

- **Claim Frequency**: {"Above average" if total_claims > 3 else "Normal"} ({total_claims} claims in 24 months)
- **Claim Amount Pattern**: {"High variance" if approved_claims > 0 and denied_claims > 0 else "Consistent"}
- **Geographic Risk**: {state} has {"elevated" if fraud_rate > 4.0 else "standard"} fraud activity

### Data-Driven Recommendations

1. {"⚠️ Review claim history carefully - multiple prior claims detected" if total_claims > 2 else "✅ Limited claim history - standard review recommended"}
2. {"⚠️ High-value claim type ({claim_type}) - enhanced verification recommended" if type_avg_claim > 20000 else "✅ Claim type has moderate risk profile"}
3. {"⚠️ Regional fraud rate elevated - additional documentation may be warranted" if fraud_rate > 4.5 else "✅ Regional fraud rate within normal range"}

---
*To enable live Fabric data, ensure user is signed in with Azure AD and has access to the Fabric workspace.*
"""


_lakehouse_service = None

def get_lakehouse_service() -> Optional[LakehouseService]:
    """Get or create singleton LakehouseService instance.
    
    Returns:
        LakehouseService if configuration is available, None otherwise
    """
    global _lakehouse_service
    
    if _lakehouse_service is None:
        if not PYODBC_AVAILABLE:
            logger.info("[LAKEHOUSE] pyodbc not available, service disabled")
            return None
            
        server = os.getenv("FABRIC_SQL_SERVER")
        if not server:
            logger.info("[LAKEHOUSE] FABRIC_SQL_SERVER not configured, service disabled")
            return None
            
        try:
            _lakehouse_service = LakehouseService()
            logger.info("[LAKEHOUSE] Service initialized")
        except Exception as e:
            logger.error(f"[LAKEHOUSE] Failed to initialize: {e}")
            return None
    
    return _lakehouse_service
