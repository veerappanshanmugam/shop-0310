"""Tests for the products and categories API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_category(client: AsyncClient):
    """POST /categories creates a category and returns it with an id."""
    response = await client.post(
        "/categories",
        json={"name": "Electronics", "description": "Electronic devices"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "Electronics"
    assert data["description"] == "Electronic devices"


@pytest.mark.asyncio
async def test_list_categories(client: AsyncClient):
    """GET /categories returns a list of all categories."""
    await client.post("/categories", json={"name": "Cat1"})
    await client.post("/categories", json={"name": "Cat2"})

    response = await client.get("/categories")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2


@pytest.mark.asyncio
async def test_create_product_with_category(client: AsyncClient):
    """POST /products with a valid category creates a product."""
    cat_resp = await client.post("/categories", json={"name": "Books"})
    category_id = cat_resp.json()["id"]

    response = await client.post(
        "/products",
        json={
            "name": "Python Guide",
            "description": "A guide to Python",
            "price": 29.99,
            "category_id": category_id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "Python Guide"
    assert float(data["price"]) == 29.99
    assert data["category_id"] == category_id
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_product_nonexistent_category(client: AsyncClient):
    """POST /products with a non-existent category returns 404."""
    response = await client.post(
        "/products",
        json={
            "name": "Ghost Product",
            "price": 10.00,
            "category_id": 9999,
        },
    )
    assert response.status_code == 404
    assert "category not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_product_by_id(client: AsyncClient):
    """GET /products/{id} returns the correct product."""
    cat_resp = await client.post("/categories", json={"name": "Toys"})
    category_id = cat_resp.json()["id"]

    create_resp = await client.post(
        "/products",
        json={
            "name": "Teddy Bear",
            "price": 15.50,
            "category_id": category_id,
        },
    )
    product_id = create_resp.json()["id"]

    response = await client.get(f"/products/{product_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == product_id
    assert data["name"] == "Teddy Bear"


@pytest.mark.asyncio
async def test_list_products(client: AsyncClient):
    """GET /products returns a list of all products."""
    cat_resp = await client.post("/categories", json={"name": "Food"})
    category_id = cat_resp.json()["id"]

    await client.post(
        "/products",
        json={"name": "Apple", "price": 1.00, "category_id": category_id},
    )
    await client.post(
        "/products",
        json={"name": "Banana", "price": 0.50, "category_id": category_id},
    )

    response = await client.get("/products")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
