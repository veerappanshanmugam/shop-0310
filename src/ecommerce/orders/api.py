"""Order management API endpoints."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from ecommerce.database import get_session
from ecommerce.models import Order, OrderItem, Product, User, Inventory

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderItemRequest(BaseModel):
    """Request model for order items."""

    product_id: int
    quantity: int


class CreateOrderRequest(BaseModel):
    """Request model for creating an order."""

    user_id: int
    items: list[OrderItemRequest]


class OrderResponse(BaseModel):
    """Response model with order details."""

    id: int
    user_id: int
    user_name: str
    status: str
    total: Decimal
    created_at: datetime
    items: list[dict]


@router.post("", response_model=OrderResponse)
async def create_order(
    request: CreateOrderRequest, session: AsyncSession = Depends(get_session)
) -> OrderResponse:
    """Create a new order with items and inventory reservation."""
    # Verify user exists
    user = await session.get(User, request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Store user name before session operations
    user_name = user.name

    # Validate products and calculate total
    total = Decimal(0)
    order_items_data = []

    for item_req in request.items:
        product = await session.get(Product, item_req.product_id)
        if not product:
            raise HTTPException(
                status_code=404, detail=f"Product {item_req.product_id} not found"
            )

        # Check inventory availability
        inventory = await session.get(Inventory, item_req.product_id)
        if not inventory:
            raise HTTPException(
                status_code=404,
                detail=f"Inventory not found for product {item_req.product_id}",
            )

        available = inventory.quantity - inventory.reserved
        if available < item_req.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient inventory for {product.name}. Available: {available}",
            )

        item_total = product.price * item_req.quantity
        total += item_total

        order_items_data.append(
            {
                "product": product,
                "quantity": item_req.quantity,
                "price": product.price,
                "inventory": inventory,
            }
        )

    # Create order
    order = Order(user_id=request.user_id, status="pending", total=total)
    session.add(order)
    await session.flush()

    # Create order items and reserve inventory
    items_response = []
    for item_data in order_items_data:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item_data["product"].id,
            quantity=item_data["quantity"],
            price=item_data["price"],
        )
        session.add(order_item)

        # Reserve inventory
        inventory = item_data["inventory"]
        inventory.reserved += item_data["quantity"]
        inventory.last_updated = datetime.now(UTC)
        session.add(inventory)

        items_response.append(
            {
                "product_id": item_data["product"].id,
                "product_name": item_data["product"].name,
                "quantity": item_data["quantity"],
                "price": float(item_data["price"]),
            }
        )

    await session.commit()
    await session.refresh(order)

    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        user_name=user_name,
        status=order.status,
        total=order.total,
        created_at=order.created_at,
        items=items_response,
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int, session: AsyncSession = Depends(get_session)
) -> OrderResponse:
    """Get order details with items."""
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Get user (cross-domain join)
    user = await session.get(User, order.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Store user name before session operations
    user_name = user.name

    # Get order items (cross-domain join)
    result = await session.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )
    order_items = result.scalars().all()

    items_response = []
    for item in order_items:
        product = await session.get(Product, item.product_id)
        if product:
            items_response.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "quantity": item.quantity,
                    "price": float(item.price),
                }
            )

    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        user_name=user_name,
        status=order.status,
        total=order.total,
        created_at=order.created_at,
        items=items_response,
    )


@router.get("", response_model=list[Order])
async def list_orders(session: AsyncSession = Depends(get_session)) -> list[Order]:
    """List all orders."""
    result = await session.execute(select(Order))
    return result.scalars().all()
