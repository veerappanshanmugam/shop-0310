"""Tests for the inventory API endpoints."""

import pytest
from httpx import AsyncClient


async def _create_product(client: AsyncClient) -> int:
    """Helper: create a category and product, return the product id."""
    cat_resp = await client.post("/categories", json={"name": "Hardware"})
    category_id = cat_resp.json()["id"]

    prod_resp = await client.post(
        "/products",
        json={
            "name": "Wrench",
            "price": 12.00,
            "category_id": category_id,
        },
    )
    return prod_resp.json()["id"]


@pytest.mark.asyncio
async def test_get_inventory_after_product_creation(client: AsyncClient):
    """GET /inventory/{product_id} returns quantity=0 after product creation."""
    product_id = await _create_product(client)

    response = await client.get(f"/inventory/{product_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == product_id
    assert data["quantity"] == 0
    assert data["reserved"] == 0


@pytest.mark.asyncio
async def test_update_inventory(client: AsyncClient):
    """PUT /inventory/{product_id} updates the quantity."""
    product_id = await _create_product(client)

    response = await client.put(
        f"/inventory/{product_id}", json={"quantity": 50}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["quantity"] == 50
    assert data["product_id"] == product_id


@pytest.mark.asyncio
async def test_reserve_inventory(client: AsyncClient):
    """POST /inventory/{product_id}/reserve increments the reserved count."""
    product_id = await _create_product(client)
    await client.put(f"/inventory/{product_id}", json={"quantity": 20})

    response = await client.post(
        f"/inventory/{product_id}/reserve", json={"quantity": 5}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reserved"] == 5
    assert data["quantity"] == 20


@pytest.mark.asyncio
async def test_reserve_more_than_available(client: AsyncClient):
    """POST /inventory/{product_id}/reserve with too many returns 400."""
    product_id = await _create_product(client)
    await client.put(f"/inventory/{product_id}", json={"quantity": 3})

    response = await client.post(
        f"/inventory/{product_id}/reserve", json={"quantity": 10}
    )
    assert response.status_code == 400
    assert "insufficient" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_nonexistent_inventory(client: AsyncClient):
    """GET /inventory/{product_id} for a non-existent product returns 404."""
    response = await client.get("/inventory/9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
