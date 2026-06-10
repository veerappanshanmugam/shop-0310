"""Tests for the users API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    """POST /users creates a user and returns it with an id."""
    response = await client.post(
        "/users",
        json={"email": "alice@example.com", "name": "Alice"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] is not None
    assert data["email"] == "alice@example.com"
    assert data["name"] == "Alice"
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_user_by_id(client: AsyncClient):
    """GET /users/{id} returns the correct user."""
    create_resp = await client.post(
        "/users",
        json={"email": "bob@example.com", "name": "Bob"},
    )
    user_id = create_resp.json()["id"]

    response = await client.get(f"/users/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["email"] == "bob@example.com"
    assert data["name"] == "Bob"


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient):
    """GET /users returns a list of all users."""
    await client.post("/users", json={"email": "u1@example.com", "name": "User1"})
    await client.post("/users", json={"email": "u2@example.com", "name": "User2"})

    response = await client.get("/users")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2


@pytest.mark.asyncio
async def test_create_duplicate_email(client: AsyncClient):
    """POST /users with a duplicate email returns 400."""
    await client.post(
        "/users",
        json={"email": "dup@example.com", "name": "First"},
    )
    response = await client.post(
        "/users",
        json={"email": "dup@example.com", "name": "Second"},
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_nonexistent_user(client: AsyncClient):
    """GET /users/{id} for a non-existent user returns 404."""
    response = await client.get("/users/9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
