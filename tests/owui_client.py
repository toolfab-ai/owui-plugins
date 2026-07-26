import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OwuiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        self.token: str | None = None

    @property
    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def close(self):
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        headers.update(self._headers)
        resp = await self._client.request(method, path, headers=headers, **kwargs)
        return resp

    async def wait_for_ready(self, timeout: int = 120) -> None:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                resp = await self._client.get("/api/auth", timeout=5.0)
                if resp.status_code == 200:
                    logger.info("Open WebUI is ready")
                    return
            except httpx.RequestError:
                pass
            await asyncio.sleep(2)
        raise TimeoutError(f"Open WebUI did not become ready within {timeout}s")

    async def signup(
        self, email: str = "admin@test.com", password: str = "testpassword123", name: str = "Admin"
    ) -> dict[str, Any]:
        resp = await self._request(
            "POST",
            "/api/v1/auths/signup",
            json={"name": name, "email": email, "password": password},
        )
        if resp.status_code == 200:
            data = resp.json()
            self.token = data["token"]
            logger.info("Signed up and authenticated as %s", email)
            return data
        raise RuntimeError(f"Signup failed ({resp.status_code}): {resp.text}")

    async def signin(
        self, email: str = "admin@test.com", password: str = "testpassword123"
    ) -> dict[str, Any]:
        resp = await self._request(
            "POST",
            "/api/v1/auths/signin",
            json={"email": email, "password": password},
        )
        if resp.status_code == 200:
            data = resp.json()
            self.token = data["token"]
            logger.info("Signed in as %s", email)
            return data
        raise RuntimeError(f"Signin failed ({resp.status_code}): {resp.text}")

    async def create_tool(
        self, tool_id: str, name: str, content: str, description: str = ""
    ) -> dict[str, Any]:
        resp = await self._request(
            "POST",
            "/api/v1/tools/create",
            json={
                "id": tool_id,
                "name": name,
                "content": content,
                "meta": {"description": description},
                "access_grants": [],
            },
        )
        if resp.status_code == 200:
            return resp.json()
        raise RuntimeError(f"Create tool failed ({resp.status_code}): {resp.text}")

    async def get_tools(self) -> list[dict[str, Any]]:
        resp = await self._request("GET", "/api/v1/tools/list")
        if resp.status_code == 200:
            return resp.json()
        raise RuntimeError(f"Get tools failed ({resp.status_code}): {resp.text}")

    async def get_tool_by_id(self, tool_id: str) -> dict[str, Any]:
        resp = await self._request("GET", f"/api/v1/tools/id/{tool_id}")
        if resp.status_code == 200:
            return resp.json()
        raise RuntimeError(f"Get tool by id failed ({resp.status_code}): {resp.text}")

    async def get_tool_valves_spec(self, tool_id: str) -> dict[str, Any]:
        resp = await self._request("GET", f"/api/v1/tools/id/{tool_id}/valves/spec")
        if resp.status_code == 200:
            return resp.json()
        raise RuntimeError(f"Get valve spec failed ({resp.status_code}): {resp.text}")

    async def update_tool_valves(self, tool_id: str, valves: dict[str, Any]) -> dict[str, Any]:
        resp = await self._request(
            "POST",
            f"/api/v1/tools/id/{tool_id}/valves/update",
            json=valves,
        )
        if resp.status_code == 200:
            return resp.json()
        raise RuntimeError(f"Update valves failed ({resp.status_code}): {resp.text}")

    async def delete_tool(self, tool_id: str) -> bool:
        resp = await self._request("DELETE", f"/api/v1/tools/id/{tool_id}/delete")
        if resp.status_code == 200:
            return resp.json()
        raise RuntimeError(f"Delete tool failed ({resp.status_code}): {resp.text}")
