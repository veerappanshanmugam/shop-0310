"""Reporting API endpoints."""

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func

from ecommerce.database import get_session
from ecommerce.models import Order, OrderItem, Product, User, Inventory, Category

router = APIRouter(prefix="/reports", tags=["reports"])


class SalesReport(BaseModel):
    """Sales summary report."""

    total_revenue: Decimal
    total_orders: int
    average_order_value: Decimal
    pending_orders: int
    completed_orders: int


class InventoryReport(BaseModel):
    """Inventory summary report."""

    total_products: int
    total_stock: int
    total_reserved: int
    available_stock: int
    low_stock_products: int


class ProductPerformance(BaseModel):
    """Product performance metrics."""

    product_id: int
    product_name: str
    category_name: str
    units_sold: int
    revenue: Decimal
    current_stock: int
    reserved: int


class CategoryPerformance(BaseModel):
    """Category performance metrics."""

    category_id: int
    category_name: str
    product_count: int
    total_revenue: Decimal
    units_sold: int


class UserActivity(BaseModel):
    """User activity metrics."""

    user_id: int
    user_name: str
    user_email: str
    total_orders: int
    total_spent: Decimal


@router.get("/sales", response_model=SalesReport)
async def get_sales_report(
    session: AsyncSession = Depends(get_session)
) -> SalesReport:
    """Get sales summary report."""
    # Total revenue and order count
    result = await session.execute(
        select(func.sum(Order.total), func.count(Order.id))
    )
    total_revenue, total_orders = result.first()

    # Count by status
    result = await session.execute(
        select(func.count(Order.id)).where(Order.status == "pending")
    )
    pending_orders = result.scalar() or 0

    result = await session.execute(
        select(func.count(Order.id)).where(Order.status == "completed")
    )
    completed_orders = result.scalar() or 0

    # Calculate average order value
    avg_order_value = Decimal(0)
    if total_orders and total_revenue:
        avg_order_value = total_revenue / total_orders

    return SalesReport(
        total_revenue=total_revenue or Decimal(0),
        total_orders=total_orders or 0,
        average_order_value=avg_order_value,
        pending_orders=pending_orders,
        completed_orders=completed_orders,
    )


@router.get("/inventory", response_model=InventoryReport)
async def get_inventory_report(
    low_stock_threshold: int = 10,
    session: AsyncSession = Depends(get_session),
) -> InventoryReport:
    """Get inventory summary report."""
    # Total products
    result = await session.execute(select(func.count(Product.id)))
    total_products = result.scalar() or 0

    # Inventory totals
    result = await session.execute(
        select(
            func.sum(Inventory.quantity),
            func.sum(Inventory.reserved)
        )
    )
    total_stock, total_reserved = result.first()
    total_stock = total_stock or 0
    total_reserved = total_reserved or 0
    available_stock = total_stock - total_reserved

    # Low stock products
    result = await session.execute(
        select(func.count(Inventory.product_id)).where(
            (Inventory.quantity - Inventory.reserved) < low_stock_threshold
        )
    )
    low_stock_products = result.scalar() or 0

    return InventoryReport(
        total_products=total_products,
        total_stock=total_stock,
        total_reserved=total_reserved,
        available_stock=available_stock,
        low_stock_products=low_stock_products,
    )


@router.get("/products", response_model=list[ProductPerformance])
async def get_product_performance(
    session: AsyncSession = Depends(get_session)
) -> list[ProductPerformance]:
    """Get product performance report."""
    # Get all products with their order data
    result = await session.execute(
        select(Product, Category, Inventory)
        .join(Category, Product.category_id == Category.id)
        .outerjoin(Inventory, Product.id == Inventory.product_id)
    )
    products_data = result.all()

    performance = []
    for product, category, inventory in products_data:
        # Get order items for this product
        result = await session.execute(
            select(
                func.sum(OrderItem.quantity),
                func.sum(OrderItem.quantity * OrderItem.price)
            ).where(OrderItem.product_id == product.id)
        )
        units_sold, revenue = result.first()

        performance.append(
            ProductPerformance(
                product_id=product.id,
                product_name=product.name,
                category_name=category.name,
                units_sold=units_sold or 0,
                revenue=revenue or Decimal(0),
                current_stock=inventory.quantity if inventory else 0,
                reserved=inventory.reserved if inventory else 0,
            )
        )

    # Sort by revenue descending
    performance.sort(key=lambda x: x.revenue, reverse=True)
    return performance


@router.get("/categories", response_model=list[CategoryPerformance])
async def get_category_performance(
    session: AsyncSession = Depends(get_session)
) -> list[CategoryPerformance]:
    """Get category performance report."""
    # Get all categories
    result = await session.execute(select(Category))
    categories = result.scalars().all()

    performance = []
    for category in categories:
        # Get products in this category
        result = await session.execute(
            select(func.count(Product.id)).where(Product.category_id == category.id)
        )
        product_count = result.scalar() or 0

        # Get order items for products in this category
        result = await session.execute(
            select(
                func.sum(OrderItem.quantity),
                func.sum(OrderItem.quantity * OrderItem.price)
            )
            .join(Product, OrderItem.product_id == Product.id)
            .where(Product.category_id == category.id)
        )
        units_sold, revenue = result.first()

        performance.append(
            CategoryPerformance(
                category_id=category.id,
                category_name=category.name,
                product_count=product_count,
                total_revenue=revenue or Decimal(0),
                units_sold=units_sold or 0,
            )
        )

    # Sort by revenue descending
    performance.sort(key=lambda x: x.total_revenue, reverse=True)
    return performance


@router.get("/users", response_model=list[UserActivity])
async def get_user_activity(
    session: AsyncSession = Depends(get_session)
) -> list[UserActivity]:
    """Get user activity report."""
    # Get all users
    result = await session.execute(select(User))
    users = result.scalars().all()

    activity = []
    for user in users:
        # Get orders for this user
        result = await session.execute(
            select(func.count(Order.id), func.sum(Order.total))
            .where(Order.user_id == user.id)
        )
        total_orders, total_spent = result.first()

        activity.append(
            UserActivity(
                user_id=user.id,
                user_name=user.name,
                user_email=user.email,
                total_orders=total_orders or 0,
                total_spent=total_spent or Decimal(0),
            )
        )

    # Sort by total spent descending
    activity.sort(key=lambda x: x.total_spent, reverse=True)
    return activity
