"""Quick diagnostic: list all workspaces visible to the SPN."""
from fabric_scanner.config import load_env, Config, get_fabric_token
import requests

load_env()
Config.reload()

token = get_fabric_token()
r = requests.get(
    "https://api.fabric.microsoft.com/v1/workspaces",
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
workspaces = r.json().get("value", [])
print(f"Total workspaces visible: {len(workspaces)}")
for ws in workspaces:
    marker = " <<<< TARGET" if ws["id"] == "68294fe5-0189-406e-9293-28c55c4b59ea" else ""
    print(f"  {ws['id']}  {ws.get('displayName','?'):40s}  capacity={ws.get('capacityId','none')}{marker}")

if not any(ws["id"] == "68294fe5-0189-406e-9293-28c55c4b59ea" for ws in workspaces):
    print("\n>> TARGET WORKSPACE NOT FOUND - SPN does not have access to it")
