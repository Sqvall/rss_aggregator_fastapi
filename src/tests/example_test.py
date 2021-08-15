import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/api")
    assert response.status_code == 200
    assert response.json() == {"Hello": "World"}
