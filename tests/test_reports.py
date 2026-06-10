"""Tests for the reports API endpoints and health check."""

from decimal import Decimal

import pytest
from httpx import AsyncClient


async def _seed_full_dataset(client: AsyncClient):
    """Helper: create users, categories, products, inventory, and orders."""
    # Create users
    u1 = await client.post(
        "/users", json={"email": "alice@example.com", "name": "Alice"}
    )
    user1_id = u1.json()["id"]

    u2 = await client.post(
        "/users", json={"email": "bob@example.com", "name": "Bob"}
    )
    user2_id = u2.json()["id"]

    # Create categories
    c1 = await client.post(
        "/categories", json={"name": "Electronics", "description": "Devices"}
    )
    cat1_id = c1.json()["id"]

    c2 = await client.post(
        "/categories", json={"name": "Books", "description": "Reading material"}
    )
    cat2_id = c2.json()["id"]

    # Create products
    p1 = await client.post(
        "/products",
        json={"name": "Laptop", "price": 1000.00, "category_id": cat1_id},
    )
    prod1_id = p1.json()["id"]

    p2 = await client.post(
        "/products",
        json={"name": "Novel", "price": 20.00, "category_id": cat2_id},
    )
    prod2_id = p2.json()["id"]

    # Set inventory
    await client.put(f"/inventory/{prod1_id}", json={"quantity": 50})
    await client.put(f"/inventory/{prod2_id}", json={"quantity": 200})

    # Create orders
    # Alice buys 2 laptops = 2000.00
    await client.post(
        "/orders",
        json={
            "user_id": user1_id,
            "items": [{"product_id": prod1_id, "quantity": 2}],
        },
    )

    # Bob buys 3 novels = 60.00
    await client.post(
        "/orders",
        json={
            "user_id": user2_id,
            "items": [{"product_id": prod2_id, "quantity": 3}],
        },
    )

    return {
        "user1_id": user1_id,
        "user2_id": user2_id,
        "cat1_id": cat1_id,
        "cat2_id": cat2_id,
        "prod1_id": prod1_id,
        "prod2_id": prod2_id,
    }


@pytest.mark.asyncio
async def test_sales_report_no_data(client: AsyncClient):
    """GET /reports/sales with no orders returns zeros."""
    response = await client.get("/reports/sales")
    assert response.status_code == 200
    data = response.json()
    assert float(data["total_revenue"]) == 0
    assert data["total_orders"] == 0
    assert float(data["average_order_value"]) == 0
    assert data["pending_orders"] == 0
    assert data["completed_orders"] == 0


@pytest.mark.asyncio
async def test_sales_report_with_orders(client: AsyncClient):
    """GET /reports/sales returns correct aggregation after orders."""
    await _seed_full_dataset(client)

    response = await client.get("/reports/sales")
    assert response.status_code == 200
    data = response.json()
    # Total: 2000.00 + 60.00 = 2060.00
    assert float(data["total_revenue"]) == 2060.00
    assert data["total_orders"] == 2
    assert float(data["average_order_value"]) == 1030.00
    assert data["pending_orders"] == 2
    assert data["completed_orders"] == 0


@pytest.mark.asyncio
async def test_inventory_report(client: AsyncClient):
    """GET /reports/inventory returns correct totals."""
    ids = await _seed_full_dataset(client)

    response = await client.get("/reports/inventory")
    assert response.status_code == 200
    data = response.json()
    assert data["total_products"] == 2
    # Stock: 50 + 200 = 250
    assert data["total_stock"] == 250
    # Reserved: 2 (laptops) + 3 (novels) = 5
    assert data["total_reserved"] == 5
    assert data["available_stock"] == 245
    # Both products have (quantity - reserved) < 10 only if low -- let's check
    # Laptop: 50 - 2 = 48, Novel: 200 - 3 = 197 -- neither is low at threshold 10
    assert data["low_stock_products"] == 0


@pytest.mark.asyncio
async def test_product_performance(client: AsyncClient):
    """GET /reports/products returns correct per-product data."""
    ids = await _seed_full_dataset(client)

    response = await client.get("/reports/products")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Results sorted by revenue desc -- Laptop (2000) first, Novel (60) second
    laptop = data[0]
    assert laptop["product_name"] == "Laptop"
    assert laptop["units_sold"] == 2
    assert float(laptop["revenue"]) == 2000.00
    assert laptop["current_stock"] == 50
    assert laptop["reserved"] == 2

    novel = data[1]
    assert novel["product_name"] == "Novel"
    assert novel["units_sold"] == 3
    assert float(novel["revenue"]) == 60.00
    assert novel["current_stock"] == 200
    assert novel["reserved"] == 3


@pytest.mark.asyncio
async def test_category_performance(client: AsyncClient):
    """GET /reports/categories returns correct per-category data."""
    ids = await _seed_full_dataset(client)

    response = await client.get("/reports/categories")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Sorted by revenue desc -- Electronics (2000) first, Books (60) second
    electronics = data[0]
    assert electronics["category_name"] == "Electronics"
    assert electronics["product_count"] == 1
    assert float(electronics["total_revenue"]) == 2000.00
    assert electronics["units_sold"] == 2

    books = data[1]
    assert books["category_name"] == "Books"
    assert books["product_count"] == 1
    assert float(books["total_revenue"]) == 60.00
    assert books["units_sold"] == 3


@pytest.mark.asyncio
async def test_user_activity(client: AsyncClient):
    """GET /reports/users returns correct per-user data."""
    ids = await _seed_full_dataset(client)

    response = await client.get("/reports/users")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Sorted by total_spent desc -- Alice (2000) first, Bob (60) second
    alice = data[0]
    assert alice["user_name"] == "Alice"
    assert alice["user_email"] == "alice@example.com"
    assert alice["total_orders"] == 1
    assert float(alice["total_spent"]) == 2000.00

    bob = data[1]
    assert bob["user_name"] == "Bob"
    assert bob["user_email"] == "bob@example.com"
    assert bob["total_orders"] == 1
    assert float(bob["total_spent"]) == 60.00


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """GET / returns the health check response."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ecommerce-monolith"
