import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import Category, CashflowItem, CashflowTransaction, User
from app.schemas.schemas import CategoryCreate, CategoryUpdate, CategoryResponse, CategoryTreeResponse
from app.services.cashflow_engine import build_category_lineage_map, convert_currency_to_eur
from app.api.deps import get_current_user

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("", response_model=List[CategoryResponse])
@router.get("/", response_model=List[CategoryResponse])
async def list_categories(
    category_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lineage_map = await build_category_lineage_map(db)
    results = []

    for cid, meta in lineage_map.items():
        cat = meta["category"]
        if category_type and cat.category_type != category_type.upper():
            continue

        results.append(CategoryResponse(
            category_id=cat.category_id,
            parent_id=cat.parent_id,
            name=cat.name,
            category_type=cat.category_type,
            default_label=cat.default_label,
            icon=cat.icon,
            color=cat.color,
            created_at=cat.created_at,
            effective_label=meta["effective_label"],
            full_path=meta["full_path"],
            level=meta["level"]
        ))

    results.sort(key=lambda x: (x.category_type, x.full_path or ""))
    return results

@router.get("/tree", response_model=List[CategoryTreeResponse])
async def get_category_tree(
    category_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lineage_map = await build_category_lineage_map(db)

    # Build node map
    node_map: Dict[int, CategoryTreeResponse] = {}
    for cid, meta in lineage_map.items():
        cat = meta["category"]
        node_map[cid] = CategoryTreeResponse(
            category_id=cat.category_id,
            parent_id=cat.parent_id,
            name=cat.name,
            category_type=cat.category_type,
            default_label=cat.default_label,
            icon=cat.icon,
            color=cat.color,
            created_at=cat.created_at,
            effective_label=meta["effective_label"],
            full_path=meta["full_path"],
            level=meta["level"],
            subcategories=[]
        )

    # Nest subcategories
    roots: List[CategoryTreeResponse] = []
    for cid, node in node_map.items():
        if node.parent_id and node.parent_id in node_map:
            node_map[node.parent_id].subcategories.append(node)
        else:
            if not category_type or node.category_type == category_type.upper():
                roots.append(node)

    return roots

@router.get("/totals")
async def get_category_totals(
    start_date: Optional[datetime.date] = Query(None),
    end_date: Optional[datetime.date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, float]:
    lineage_map = await build_category_lineage_map(db)
    stmt = select(CashflowTransaction).options(selectinload(CashflowTransaction.items))
    if start_date:
        stmt = stmt.where(CashflowTransaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(CashflowTransaction.transaction_date <= end_date)
    res = await db.execute(stmt)
    transactions = res.scalars().all()

    totals: Dict[str, float] = {str(cid): 0.0 for cid in lineage_map}
    for tx in transactions:
        for item in tx.items:
            meta = lineage_map.get(item.category_id)
            if not meta or meta["category"].category_type == "TRANSFER":
                continue
            raw_amt = float(item.amount or 0.0)
            amt = convert_currency_to_eur(raw_amt, tx.currency or "EUR")
            # Accumulate for self and all ancestors
            for anc in meta["ancestors"]:
                k = str(anc.category_id)
                totals[k] = round(totals.get(k, 0.0) + amt, 2)
    return totals

@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lineage_map = await build_category_lineage_map(db)
    meta = lineage_map.get(category_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Category not found")

    cat = meta["category"]
    return CategoryResponse(
        category_id=cat.category_id,
        parent_id=cat.parent_id,
        name=cat.name,
        category_type=cat.category_type,
        default_label=cat.default_label,
        icon=cat.icon,
        color=cat.color,
        created_at=cat.created_at,
        effective_label=meta["effective_label"],
        full_path=meta["full_path"],
        level=meta["level"]
    )

@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_in: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cat_dict = category_in.model_dump()
    cat_dict["category_type"] = cat_dict.get("category_type", "EXPENSE").upper()

    if cat_dict.get("parent_id"):
        parent_stmt = select(Category).where(Category.category_id == cat_dict["parent_id"])
        parent_res = await db.execute(parent_stmt)
        parent = parent_res.scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=400, detail="Parent category does not exist")
        # Ensure category_type matches parent
        cat_dict["category_type"] = parent.category_type

    category = Category(**cat_dict)
    db.add(category)
    await db.commit()
    await db.refresh(category)

    lineage_map = await build_category_lineage_map(db)
    meta = lineage_map[category.category_id]

    return CategoryResponse(
        category_id=category.category_id,
        parent_id=category.parent_id,
        name=category.name,
        category_type=category.category_type,
        default_label=category.default_label,
        icon=category.icon,
        color=category.color,
        created_at=category.created_at,
        effective_label=meta["effective_label"],
        full_path=meta["full_path"],
        level=meta["level"]
    )

@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_in: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Category).where(Category.category_id == category_id)
    res = await db.execute(stmt)
    category = res.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    update_data = category_in.model_dump(exclude_unset=True)
    if "parent_id" in update_data:
        new_parent_id = update_data["parent_id"]
        if new_parent_id is not None:
            if new_parent_id == category_id:
                raise HTTPException(status_code=400, detail="A category cannot be its own parent")

            # Fetch all categories to check existence and prevent cycles
            all_cats_res = await db.execute(select(Category))
            all_cats = all_cats_res.scalars().all()
            cat_by_id = {c.category_id: c for c in all_cats}

            if new_parent_id not in cat_by_id:
                raise HTTPException(status_code=400, detail="Parent category does not exist")

            # Traverse ancestry of candidate parent to ensure category_id is not in its lineage (no cycles)
            curr_p = new_parent_id
            visited = set()
            while curr_p and curr_p not in visited:
                if curr_p == category_id:
                    raise HTTPException(status_code=400, detail="Cannot set a descendant category as parent (cycle detected)")
                visited.add(curr_p)
                parent_node = cat_by_id.get(curr_p)
                curr_p = parent_node.parent_id if parent_node else None

    for field, val in update_data.items():
        setattr(category, field, val)

    await db.commit()
    await db.refresh(category)

    lineage_map = await build_category_lineage_map(db)
    meta = lineage_map[category.category_id]

    return CategoryResponse(
        category_id=category.category_id,
        parent_id=category.parent_id,
        name=category.name,
        category_type=category.category_type,
        default_label=category.default_label,
        icon=category.icon,
        color=category.color,
        created_at=category.created_at,
        effective_label=meta["effective_label"],
        full_path=meta["full_path"],
        level=meta["level"]
    )

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Category).where(Category.category_id == category_id)
    res = await db.execute(stmt)
    category = res.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check if category has subcategories
    subcat_stmt = select(func.count(Category.category_id)).where(Category.parent_id == category_id)
    subcat_res = await db.execute(subcat_stmt)
    if (subcat_res.scalar() or 0) > 0:
        raise HTTPException(status_code=400, detail="Cannot delete category that has subcategories. Please reassign or delete subcategories first.")

    # Check if category is used in cashflow items
    used_stmt = select(func.count(CashflowItem.item_id)).where(CashflowItem.category_id == category_id)
    used_res = await db.execute(used_stmt)
    if (used_res.scalar() or 0) > 0:
        raise HTTPException(status_code=400, detail="Cannot delete category that is used in transactions.")

    await db.delete(category)
    await db.commit()
