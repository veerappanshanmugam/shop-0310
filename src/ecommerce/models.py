"""All database models - monolithic design with shared models."""

from datetime import UTC, datetime
from decimal import Decimal
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """User account."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Category(SQLModel, table=True):
    """Product category."""

    __tablename__ = "categories"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    description: str | None = None


class Product(SQLModel, table=True):
    """Product in catalog."""

    __tablename__ = "products"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None = None
    price: Decimal = Field(decimal_places=2)
    category_id: int | None = Field(default=None, foreign_key="categories.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Inventory(SQLModel, table=True):
    """Product inventory tracking."""

    __tablename__ = "inventory"

    product_id: int = Field(foreign_key="products.id", primary_key=True)
    quantity: int = Field(default=0)
    reserved: int = Field(default=0)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Order(SQLModel, table=True):
    """Customer order."""

    __tablename__ = "orders"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    status: str = Field(default="pending")  # pending, confirmed, shipped, delivered
    total: Decimal = Field(decimal_places=2)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrderItem(SQLModel, table=True):
    """Items in an order."""

    __tablename__ = "order_items"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id")
    product_id: int = Field(foreign_key="products.id")
    quantity: int
    price: Decimal = Field(decimal_places=2)
