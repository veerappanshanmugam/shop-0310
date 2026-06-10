"""Inventory management API endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from ecommerce.database import get_session
from ecommerce.models import Inventory

router = APIRouter(prefix="/inventory", tags=["inventory"])


class InventoryUpdate(BaseModel):
    """Request model for updating inventory."""

    quantity: int


class ReserveRequest(BaseModel):
    """Request model for reserving inventory."""

    quantity: int


@router.get("/{product_id}", response_model=Inventory)
async def get_inventory(
    product_id: int, session: AsyncSession = Depends(get_session)
) -> Inventory:
    """Get inventory for a product."""
    inventory = await session.get(Inventory, product_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    return inventory


@router.put("/{product_id}", response_model=Inventory)
async def update_inventory(
    product_id: int,
    update: InventoryUpdate,
    session: AsyncSession = Depends(get_session),
) -> Inventory:
    """Update inventory quantity."""
    inventory = await session.get(Inventory, product_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    inventory.quantity = update.quantity
    inventory.last_updated = datetime.now(UTC)
    session.add(inventory)
    await session.commit()
    await session.refresh(inventory)
    return inventory


@router.post("/{product_id}/reserve", response_model=Inventory)
async def reserve_inventory(
    product_id: int,
    reserve: ReserveRequest,
    session: AsyncSession = Depends(get_session),
) -> Inventory:
    """Reserve inventory for an order."""
    inventory = await session.get(Inventory, product_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    available = inventory.quantity - inventory.reserved
    if available < reserve.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient inventory. Available: {available}, Requested: {reserve.quantity}",
        )

    inventory.reserved += reserve.quantity
    inventory.last_updated = datetime.now(UTC)
    session.add(inventory)
    await session.commit()
    await session.refresh(inventory)
    return inventory
