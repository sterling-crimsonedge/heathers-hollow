"""Starter player inventory data for giftable prototype items."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class InventoryItem:
    item_id: str
    display_name: str
    category: str
    tags: tuple[str, ...]
    quantity: int
    gift_prompt: str
    sort_order: int


STARTER_INVENTORY: tuple[InventoryItem, ...] = (
    InventoryItem(
        item_id="dusty_rose",
        display_name="Dusty Rose",
        category="flower",
        tags=("flower", "garden", "soft_color", "handmade"),
        quantity=1,
        gift_prompt="A soft dusty rose picked from Heather's garden.",
        sort_order=10,
    ),
    InventoryItem(
        item_id="chamomile_bundle",
        display_name="Chamomile Bundle",
        category="herb",
        tags=("flower", "tea", "garden", "handmade"),
        quantity=1,
        gift_prompt="A small bundle of chamomile tied with cotton thread.",
        sort_order=20,
    ),
    InventoryItem(
        item_id="porcelain_button",
        display_name="Porcelain Button",
        category="keepsake",
        tags=("porcelain", "handmade", "soft_color"),
        quantity=1,
        gift_prompt="A tiny glazed porcelain button with a pale blue flower.",
        sort_order=30,
    ),
    InventoryItem(
        item_id="smooth_pebble",
        display_name="Smooth Pebble",
        category="trinket",
        tags=("stone", "smooth", "pocket"),
        quantity=1,
        gift_prompt="A small smooth pebble from the path near the garden.",
        sort_order=40,
    ),
)


def starter_inventory_items() -> list[InventoryItem]:
    return sorted(STARTER_INVENTORY, key=lambda item: (item.sort_order, item.item_id))


def inventory_item_by_id(item_id: str) -> InventoryItem | None:
    clean_item_id = str(item_id or "").strip().lower()
    for item in STARTER_INVENTORY:
        if item.item_id == clean_item_id:
            return item
    return None


def public_inventory_item_payload(item: InventoryItem) -> dict[str, object]:
    return {
        "item_id": item.item_id,
        "display_name": item.display_name,
        "category": item.category,
        "tags": list(item.tags),
        "quantity": item.quantity,
        "gift_prompt": item.gift_prompt,
    }


def starter_inventory_payload() -> list[dict[str, object]]:
    return [public_inventory_item_payload(item) for item in starter_inventory_items()]


def normalize_gift_item(item: Mapping[str, Any] | None) -> dict[str, object]:
    """Return safe gift fields, preferring server catalog values for known starter ids."""
    raw_item = dict(item or {})
    raw_item_id = str(raw_item.get("item_id") or "").strip().lower()
    catalog_item = inventory_item_by_id(raw_item_id)
    if catalog_item is not None:
        return public_inventory_item_payload(catalog_item)

    display_name = str(raw_item.get("display_name") or raw_item_id or "something").strip()
    item_id = raw_item_id or display_name.lower().replace(" ", "_")
    category = str(raw_item.get("category") or "misc").strip().lower() or "misc"
    raw_tags = raw_item.get("tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    if not isinstance(raw_tags, (list, tuple, set)):
        raw_tags = []
    tags = [str(tag).strip().lower() for tag in raw_tags if str(tag).strip()]

    try:
        quantity = int(raw_item.get("quantity") or 1)
    except (TypeError, ValueError):
        quantity = 1
    quantity = max(1, quantity)

    gift_prompt = str(raw_item.get("gift_prompt") or f"A small gift called {display_name}.").strip()
    return {
        "item_id": item_id,
        "display_name": display_name,
        "category": category,
        "tags": tags,
        "quantity": quantity,
        "gift_prompt": gift_prompt,
    }
