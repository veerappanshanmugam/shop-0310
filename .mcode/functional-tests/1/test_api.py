"""Functional tests for the shop-0310 e-commerce backend API.

Tests cover all endpoints across users, categories, products, orders,
inventory, and reports domains. Each test is self-contained and uses
unique data to avoid collisions when running against a live server.
"""

import time
import uuid
import requests
import pytest

BASE_URL = "http://localhost:8000"
TIMEOUT = 10


def unique_email():
    """Generate a unique email to avoid duplicate conflicts."""
    return f"ft_{uuid.uuid4().hex[:12]}@test.com"


def unique_name(prefix="FT"):
    """Generate a unique name."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def health_check():
    """Confirm the app is reachable before running tests."""
    resp = requests.get(f"{BASE_URL}/", timeout=5)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["service"] == "ecommerce-monolith"


# ────────────────── Health Check ──────────────────


class TestHealthCheck:
    """GET / — health check endpoint."""

    def test_health_check_happy_path(self):
        resp = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["service"] == "ecommerce-monolith"


# ────────────────── Users ──────────────────


class TestCreateUser:
    """POST /users — create user endpoint."""

    def test_create_user_happy_path(self):
        payload = {"email": unique_email(), "name": unique_name("User")}
        resp = requests.post(f"{BASE_URL}/users", json=payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == payload["email"]
        assert body["name"] == payload["name"]
        assert "id" in body
        assert "created_at" in body

    def test_create_user_duplicate_email(self):
        email = unique_email()
        payload = {"email": email, "name": unique_name("User")}
        resp1 = requests.post(f"{BASE_URL}/users", json=payload, timeout=TIMEOUT)
        assert resp1.status_code == 200

        payload2 = {"email": email, "name": unique_name("User")}
        resp2 = requests.post(f"{BASE_URL}/users", json=payload2, timeout=TIMEOUT)
        assert resp2.status_code == 400
        body = resp2.json()
        assert "detail" in body

    def test_create_user_missing_email(self):
        payload = {"name": unique_name("User")}
        resp = requests.post(f"{BASE_URL}/users", json=payload, timeout=TIMEOUT)
        # Origin returns 500 (SQLModel crashes on missing required field),
        # target may return 422 (improved validation in newer FastAPI/SQLModel).
        assert resp.status_code in (422, 500)

    def test_create_user_missing_name(self):
        payload = {"email": unique_email()}
        resp = requests.post(f"{BASE_URL}/users", json=payload, timeout=TIMEOUT)
        assert resp.status_code in (422, 500)


class TestGetUser:
    """GET /users/{user_id} — get user by ID."""

    def test_get_user_happy_path(self):
        payload = {"email": unique_email(), "name": unique_name("User")}
        create_resp = requests.post(f"{BASE_URL}/users", json=payload, timeout=TIMEOUT)
        user_id = create_resp.json()["id"]

        resp = requests.get(f"{BASE_URL}/users/{user_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == user_id
        assert body["email"] == payload["email"]
        assert body["name"] == payload["name"]

    def test_get_user_not_found(self):
        resp = requests.get(f"{BASE_URL}/users/999999", timeout=TIMEOUT)
        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body


class TestListUsers:
    """GET /users — list all users."""

    def test_list_users_happy_path(self):
        # Create a user to ensure list is not empty
        payload = {"email": unique_email(), "name": unique_name("User")}
        requests.post(f"{BASE_URL}/users", json=payload, timeout=TIMEOUT)

        resp = requests.get(f"{BASE_URL}/users", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0


# ────────────────── Categories ──────────────────


class TestCreateCategory:
    """POST /categories — create category."""

    def test_create_category_happy_path(self):
        payload = {"name": unique_name("Cat"), "description": "Test category"}
        resp = requests.post(f"{BASE_URL}/categories", json=payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == payload["name"]
        assert body["description"] == payload["description"]
        assert "id" in body

    def test_create_category_no_description(self):
        payload = {"name": unique_name("Cat")}
        resp = requests.post(f"{BASE_URL}/categories", json=payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["description"] is None

    def test_create_category_missing_name(self):
        payload = {"description": "No name"}
        resp = requests.post(f"{BASE_URL}/categories", json=payload, timeout=TIMEOUT)
        assert resp.status_code in (422, 500)


class TestListCategories:
    """GET /categories — list all categories."""

    def test_list_categories_happy_path(self):
        payload = {"name": unique_name("Cat"), "description": "Test"}
        requests.post(f"{BASE_URL}/categories", json=payload, timeout=TIMEOUT)

        resp = requests.get(f"{BASE_URL}/categories", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0


# ────────────────── Products ──────────────────


class TestCreateProduct:
    """POST /products — create product."""

    def test_create_product_happy_path(self):
        # Create category first
        cat = requests.post(
            f"{BASE_URL}/categories",
            json={"name": unique_name("Cat")},
            timeout=TIMEOUT,
        ).json()

        payload = {"name": unique_name("Prod"), "price": 29.99, "category_id": cat["id"]}
        resp = requests.post(f"{BASE_URL}/products", json=payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == payload["name"]
        assert "id" in body
        assert body["category_id"] == cat["id"]

    def test_create_product_auto_creates_inventory(self):
        cat = requests.post(
            f"{BASE_URL}/categories",
            json={"name": unique_name("Cat")},
            timeout=TIMEOUT,
        ).json()

        payload = {"name": unique_name("Prod"), "price": 10.00, "category_id": cat["id"]}
        prod_resp = requests.post(f"{BASE_URL}/products", json=payload, timeout=TIMEOUT)
        product_id = prod_resp.json()["id"]

        inv_resp = requests.get(f"{BASE_URL}/inventory/{product_id}", timeout=TIMEOUT)
        assert inv_resp.status_code == 200
        inv_body = inv_resp.json()
        assert inv_body["product_id"] == product_id
        assert inv_body["quantity"] == 0
        assert inv_body["reserved"] == 0

    def test_create_product_nonexistent_category(self):
        payload = {"name": unique_name("Prod"), "price": 10.00, "category_id": 999999}
        resp = requests.post(f"{BASE_URL}/products", json=payload, timeout=TIMEOUT)
        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body

    def test_create_product_missing_name(self):
        payload = {"price": 10.00}
        resp = requests.post(f"{BASE_URL}/products", json=payload, timeout=TIMEOUT)
        assert resp.status_code in (422, 500)

    def test_create_product_missing_price(self):
        payload = {"name": unique_name("Prod")}
        resp = requests.post(f"{BASE_URL}/products", json=payload, timeout=TIMEOUT)
        assert resp.status_code in (422, 500)


class TestGetProduct:
    """GET /products/{product_id} — get product by ID."""

    def test_get_product_happy_path(self):
        cat = requests.post(
            f"{BASE_URL}/categories",
            json={"name": unique_name("Cat")},
            timeout=TIMEOUT,
        ).json()
        prod = requests.post(
            f"{BASE_URL}/products",
            json={"name": unique_name("Prod"), "price": 15.00, "category_id": cat["id"]},
            timeout=TIMEOUT,
        ).json()

        resp = requests.get(f"{BASE_URL}/products/{prod['id']}", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == prod["id"]
        assert body["name"] == prod["name"]

    def test_get_product_not_found(self):
        resp = requests.get(f"{BASE_URL}/products/999999", timeout=TIMEOUT)
        assert resp.status_code == 404


class TestListProducts:
    """GET /products — list all products."""

    def test_list_products_happy_path(self):
        resp = requests.get(f"{BASE_URL}/products", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)


# ────────────────── Inventory ──────────────────


class TestGetInventory:
    """GET /inventory/{product_id} — get inventory."""

    def test_get_inventory_happy_path(self):
        cat = requests.post(
            f"{BASE_URL}/categories",
            json={"name": unique_name("Cat")},
            timeout=TIMEOUT,
        ).json()
        prod = requests.post(
            f"{BASE_URL}/products",
            json={"name": unique_name("Prod"), "price": 5.00, "category_id": cat["id"]},
            timeout=TIMEOUT,
        ).json()

        resp = requests.get(f"{BASE_URL}/inventory/{prod['id']}", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["product_id"] == prod["id"]
        assert body["quantity"] == 0

    def test_get_inventory_not_found(self):
        resp = requests.get(f"{BASE_URL}/inventory/999999", timeout=TIMEOUT)
        assert resp.status_code == 404


class TestUpdateInventory:
    """PUT /inventory/{product_id} — update inventory."""

    def test_update_inventory_happy_path(self):
        cat = requests.post(
            f"{BASE_URL}/categories",
            json={"name": unique_name("Cat")},
            timeout=TIMEOUT,
        ).json()
        prod = requests.post(
            f"{BASE_URL}/products",
            json={"name": unique_name("Prod"), "price": 5.00, "category_id": cat["id"]},
            timeout=TIMEOUT,
        ).json()

        resp = requests.put(
            f"{BASE_URL}/inventory/{prod['id']}",
            json={"quantity": 50},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["quantity"] == 50
        assert body["product_id"] == prod["id"]

    def test_update_inventory_not_found(self):
        resp = requests.put(
            f"{BASE_URL}/inventory/999999",
            json={"quantity": 10},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 404


class TestReserveInventory:
    """POST /inventory/{product_id}/reserve — reserve inventory."""

    def test_reserve_inventory_happy_path(self):
        cat = requests.post(
            f"{BASE_URL}/categories",
            json={"name": unique_name("Cat")},
            timeout=TIMEOUT,
        ).json()
        prod = requests.post(
            f"{BASE_URL}/products",
            json={"name": unique_name("Prod"), "price": 5.00, "category_id": cat["id"]},
            timeout=TIMEOUT,
        ).json()
        # Set inventory
        requests.put(
            f"{BASE_URL}/inventory/{prod['id']}",
            json={"quantity": 100},
            timeout=TIMEOUT,
        )

        resp = requests.post(
            f"{BASE_URL}/inventory/{prod['id']}/reserve",
            json={"quantity": 10},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["reserved"] == 10
        assert body["quantity"] == 100

    def test_reserve_inventory_insufficient(self):
        cat = requests.post(
            f"{BASE_URL}/categories",
            json={"name": unique_name("Cat")},
            timeout=TIMEOUT,
        ).json()
        prod = requests.post(
            f"{BASE_URL}/products",
            json={"name": unique_name("Prod"), "price": 5.00, "category_id": cat["id"]},
            timeout=TIMEOUT,
        ).json()
        # Inventory starts at 0, try to reserve
        resp = requests.post(
            f"{BASE_URL}/inventory/{prod['id']}/reserve",
            json={"quantity": 5},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "detail" in body

    def test_reserve_inventory_not_found(self):
        resp = requests.post(
            f"{BASE_URL}/inventory/999999/reserve",
            json={"quantity": 1},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 404


# ────────────────── Orders ──────────────────


class TestCreateOrder:
    """POST /orders — create order."""

    def test_create_order_happy_path(self):
        # Setup: user, category, product, inventory
        user = requests.post(
            f"{BASE_URL}/users",
            json={"email": unique_email(), "name": unique_name("User")},
            timeout=TIMEOUT,
        ).json()
        cat = requests.post(
            f"{BASE_URL}/categories",
            json={"name": unique_name("Cat")},
            timeout=TIMEOUT,
        ).json()
        prod = requests.post(
            f"{BASE_URL}/products",
            json={"name": unique_name("Prod"), "price": 25.00, "category_id": cat["id"]},
            timeout=TIMEOUT,
        ).json()
        requests.put(
            f"{BASE_URL}/inventory/{prod['id']}",
            json={"quantity": 100},
            timeout=TIMEOUT,
        )

        payload = {
            "user_id": user["id"],
            "items": [{"product_id": prod["id"], "quantity": 2}],
        }
        resp = requests.post(f"{BASE_URL}/orders", json=payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == user["id"]
        assert body["status"] == "pending"
        assert len(body["items"]) == 1
        assert body["items"][0]["product_id"] == prod["id"]
        assert body["items"][0]["quantity"] == 2

    def test_create_order_reserves_inventory(self):
        user = requests.post(
            f"{BASE_URL}/users",
            json={"email": unique_email(), "name": unique_name("User")},
            timeout=TIMEOUT,
        ).json()
        cat = requests.post(
            f"{BASE_URL}/categories",
            json={"name": unique_name("Cat")},
            timeout=TIMEOUT,
        ).json()
        prod = requests.post(
            f"{BASE_URL}/products",
            json={"name": unique_name("Prod"), "price": 10.00, "category_id": cat["id"]},
            timeout=TIMEOUT,
        ).json()
        requests.put(
            f"{BASE_URL}/inventory/{prod['id']}",
            json={"quantity": 50},
            timeout=TIMEOUT,
        )

        payload = {
            "user_id": user["id"],
            "items": [{"product_id": prod["id"], "quantity": 3}],
        }
        requests.post(f"{BASE_URL}/orders", json=payload, timeout=TIMEOUT)

        # Check inventory reservation
        inv_resp = requests.get(f"{BASE_URL}/inventory/{prod['id']}", timeout=TIMEOUT)
        inv_body = inv_resp.json()
        assert inv_body["reserved"] == 3

    def test_create_order_user_not_found(self):
        payload = {
            "user_id": 999999,
            "items": [{"product_id": 1, "quantity": 1}],
        }
        resp = requests.post(f"{BASE_URL}/orders", json=payload, timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_create_order_insufficient_inventory(self):
        user = requests.post(
            f"{BASE_URL}/users",
            json={"email": unique_email(), "name": unique_name("User")},
            timeout=TIMEOUT,
        ).json()
        cat = requests.post(
            f"{BASE_URL}/categories",
            json={"name": unique_name("Cat")},
            timeout=TIMEOUT,
        ).json()
        prod = requests.post(
            f"{BASE_URL}/products",
            json={"name": unique_name("Prod"), "price": 10.00, "category_id": cat["id"]},
            timeout=TIMEOUT,
        ).json()
        # Inventory is 0, try to order 5
        payload = {
            "user_id": user["id"],
            "items": [{"product_id": prod["id"], "quantity": 5}],
        }
        resp = requests.post(f"{BASE_URL}/orders", json=payload, timeout=TIMEOUT)
        assert resp.status_code == 400


class TestGetOrder:
    """GET /orders/{order_id} — get order details."""

    def test_get_order_happy_path(self):
        user = requests.post(
            f"{BASE_URL}/users",
            json={"email": unique_email(), "name": unique_name("User")},
            timeout=TIMEOUT,
        ).json()
        cat = requests.post(
            f"{BASE_URL}/categories",
            json={"name": unique_name("Cat")},
            timeout=TIMEOUT,
        ).json()
        prod = requests.post(
            f"{BASE_URL}/products",
            json={"name": unique_name("Prod"), "price": 20.00, "category_id": cat["id"]},
            timeout=TIMEOUT,
        ).json()
        requests.put(
            f"{BASE_URL}/inventory/{prod['id']}",
            json={"quantity": 100},
            timeout=TIMEOUT,
        )
        order = requests.post(
            f"{BASE_URL}/orders",
            json={"user_id": user["id"], "items": [{"product_id": prod["id"], "quantity": 1}]},
            timeout=TIMEOUT,
        ).json()

        resp = requests.get(f"{BASE_URL}/orders/{order['id']}", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == order["id"]
        assert body["user_id"] == user["id"]
        assert len(body["items"]) == 1

    def test_get_order_not_found(self):
        resp = requests.get(f"{BASE_URL}/orders/999999", timeout=TIMEOUT)
        assert resp.status_code == 404


class TestListOrders:
    """GET /orders — list all orders."""

    def test_list_orders_happy_path(self):
        resp = requests.get(f"{BASE_URL}/orders", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)


# ────────────────── Reports ──────────────────


class TestSalesReport:
    """GET /reports/sales — sales summary."""

    def test_sales_report_happy_path(self):
        resp = requests.get(f"{BASE_URL}/reports/sales", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert "total_revenue" in body
        assert "total_orders" in body
        assert "average_order_value" in body
        assert "pending_orders" in body
        assert "completed_orders" in body


class TestInventoryReport:
    """GET /reports/inventory — inventory summary."""

    def test_inventory_report_happy_path(self):
        resp = requests.get(f"{BASE_URL}/reports/inventory", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert "total_products" in body
        assert "total_stock" in body
        assert "total_reserved" in body
        assert "available_stock" in body
        assert "low_stock_products" in body

    def test_inventory_report_custom_threshold(self):
        resp = requests.get(
            f"{BASE_URL}/reports/inventory",
            params={"low_stock_threshold": 5},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "low_stock_products" in body


class TestProductPerformance:
    """GET /reports/products — product performance."""

    def test_product_performance_happy_path(self):
        resp = requests.get(f"{BASE_URL}/reports/products", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)


class TestCategoryPerformance:
    """GET /reports/categories — category performance."""

    def test_category_performance_happy_path(self):
        resp = requests.get(f"{BASE_URL}/reports/categories", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)


class TestUserActivity:
    """GET /reports/users — user activity."""

    def test_user_activity_happy_path(self):
        resp = requests.get(f"{BASE_URL}/reports/users", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
