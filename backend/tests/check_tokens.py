import asyncio
import sys
sys.path.insert(0, r'C:\temp\AI\insurance-multi-agent\backend')

from app.services.cosmos_service import get_cosmos_service

async def check_tokens():
    cs = await get_cosmos_service()
    
    if not cs._token_usage_container:
        print('Token usage container not available')
        return
    
    print('\n=== TOKEN USAGE RECORDS ===')
    items = list(cs._token_usage_container.query_items(
        'SELECT * FROM c ORDER BY c._ts DESC OFFSET 0 LIMIT 10',
        enable_cross_partition_query=True
    ))
    
    if not items:
        print('No token usage records found in database')
    else:
        print(f'Found {len(items)} token usage records:\n')
        for item in items:
            print(f'Timestamp: {item.get("timestamp")}')
            print(f'Execution ID: {item.get("execution_id")}')
            print(f'Operation: {item.get("operation_name", "N/A")}')
            print(f'Total Tokens: {item.get("total_tokens", 0)}')
            print(f'Prompt Tokens: {item.get("prompt_tokens", 0)}')
            print(f'Completion Tokens: {item.get("completion_tokens", 0)}')
            print(f'Estimated Cost: $' + str(item.get("estimated_cost", 0)))
            print('-' * 50)

if __name__ == '__main__':
    asyncio.run(check_tokens())
