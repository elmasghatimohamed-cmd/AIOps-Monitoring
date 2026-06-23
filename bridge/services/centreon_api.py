import httpx
from typing import Optional
from bridge.config import CENTREON_BASE_URL, CENTREON_USERNAME, CENTREON_PASSWORD

class CentreonClient:
    def __init__(self):
        self.base_url = CENTREON_BASE_URL.rstrip('/')
        self.username = CENTREON_USERNAME
        self.password = CENTREON_PASSWORD
        self.auth_token: Optional[str] = None
        self.client: Optional[httpx.AsyncClient] = None

    async def init_client(self):
        """Initializing the persistent async HTTP session client."""
        if not self.client:
            self.client = httpx.AsyncClient(timeout=10.0, verify=False)

    async def close_client(self):
        if self.client:
            await self.client.aclose()

    async def authenticate(self) -> bool:
        """Retrieving a secure validation token via Centreon API."""
        await self.init_client()
        url = f"{self.base_url}/api/latest/login"
        payload = {"security": {"credentials": {"login": self.username, "password": self.password}}}
        
        try:
            response = await self.client.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                # Extract the token string from the nested structure
                self.auth_token = data.get("security", {}).get("token")
                print("Token refreshed successfully via X-AUTH-TOKEN exchange.")
                return True
            print(f"Auth failed with status {response.status_code}: {response.text}")
            return False
        except Exception as e:
            print(f"Auth exception encountered: {str(e)}")
            return False

    async def fetch_resource_statuses(self) -> list:
        """Quering live monitoring endpoints using valid authorization headers."""
        await self.init_client()
        if not self.auth_token:
            authenticated = await self.authenticate()
            if not authenticated:
                return []

        url = f"{self.base_url}/api/latest/monitoring/resources"
        
        headers = {
            "X-AUTH-TOKEN": self.auth_token,
            "Content-Type": "application/json"
        }
        
        params = {
            "limit": "40" 
        }

        try:
            response = await self.client.get(url, headers=headers, params=params)
            
            # Handle token timeouts
            if response.status_code == 401:
                print("🔄 [Centreon API]: Token expired. Executing re-authentication...")
                if await self.authenticate():
                    headers["X-AUTH-TOKEN"] = self.auth_token
                    response = await self.client.get(url, headers=headers, params=params)
                else:
                    return []

            if response.status_code == 200:
                return response.json().get("result", [])
            
            print(f"Resource view failed with HTTP Status: {response.status_code}")
            return []

        except Exception as e:
            print(f"Monitoring endpoint request error: {str(e)}")
            return []

centreon_api_client = CentreonClient()