"""Tests for the orders API endpoints."""

import pytest
from httpx import AsyncClient


async def _setup_order_prerequisites(client: AsyncClient):
    """Helper: create user, category, product, and set inventory for ordering."""
    # Create user
    user_resp = await client.post(
        "/users", json={"email": "buyer@example.com", "name": "Buyer"}
    )
    user_id = user_resp.json()["id"]

    # Create category
    cat_resp = await client.post("/categories", json={"name": "Gadgets"})
    category_id = cat_resp.json()["id"]

    # Create product (auto-creates inventory with quantity=0)
    prod_resp = await client.post(
        "/products",
        json={
            "name": "Widget",
            "price": 25.00,
            "category_id": category_id,
        },
    )
    product_id = prod_resp.json()["id"]

    # Update inventory so there is stock available
    await client.put(f"/inventory/{product_id}", json={"quantity": 100})

    return user_id, product_id


@pytest.mark.asyncio
async def test_create_order_full_flow(client: AsyncClient):
    """POST /orders creates an order through the full flow."""
    user_id, product_id = await _setup_order_prerequisites(client)

    response = await client.post(
        "/orders",
        json={
            "user_id": user_id,
            "items": [{"product_id": product_id, "quantity": 2}],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] is not None
    assert data["user_id"] == user_id
    assert data["user_name"] == "Buyer"
    assert data["status"] == "pending"
    assert float(data["total"]) == 50.00
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == product_id
    assert data["items"][0]["product_name"] == "Widget"
    assert data["items"][0]["quantity"] == 2
    assert float(data["items"][0]["price"]) == 25.00
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_order_by_id(client: AsyncClient):
    """GET /orders/{id} returns the correct order with details."""
    user_id, product_id = await _setup_order_prerequisites(client)

    create_resp = await client.post(
        "/orders",
        json={
            "user_id": user_id,
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    order_id = create_resp.json()["id"]

    response = await client.get(f"/orders/{order_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == order_id
    assert data["user_id"] == user_id
    assert data["user_name"] == "Buyer"
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_list_orders(client: AsyncClient):
    """GET /orders returns a list of all orders."""
    user_id, product_id = await _setup_order_prerequisites(client)

    await client.post(
        "/orders",
        json={
            "user_id": user_id,
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    await client.post(
        "/orders",
        json={
            "user_id": user_id,
            "items": [{"product_id": product_id, "quantity": 2}],
        },
    )

    response = await client.get("/orders")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2


@pytest.mark.asyncio
async def test_create_order_nonexistent_user(client: AsyncClient):
    """POST /orders with a non-existent user returns 404."""
    # Need a valid product first
    cat_resp = await client.post("/categories", json={"name": "Misc"})
    prod_resp = await client.post(
        "/products",
        json={"name": "Thing", "price": 5.00, "category_id": cat_resp.json()["id"]},
    )
    product_id = prod_resp.json()["id"]
    await client.put(f"/inventory/{product_id}", json={"quantity": 10})

    response = await client.post(
        "/orders",
        json={
            "user_id": 9999,
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert response.status_code == 404
    assert "user not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_order_nonexistent_product(client: AsyncClient):
    """POST /orders with a non-existent product returns 404."""
    user_resp = await client.post(
        "/users", json={"email": "nostock@example.com", "name": "NoStock"}
    )
    user_id = user_resp.json()["id"]

    response = await client.post(
        "/orders",
        json={
            "user_id": user_id,
            "items": [{"product_id": 9999, "quantity": 1}],
        },
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_order_insufficient_inventory(client: AsyncClient):
    """POST /orders with insufficient inventory returns 400."""
    user_id, product_id = await _setup_order_prerequisites(client)

    # Try to order more than available (100 in stock)
    response = await client.post(
        "/orders",
        json={
            "user_id": user_id,
            "items": [{"product_id": product_id, "quantity": 999}],
        },
    )
    assert response.status_code == 400
    assert "insufficient" in response.json()["detail"].lower()
