"""FastAPI service exposing barcode lookup and dish inference endpoints."""

from __future__ import annotations

from typing import Any, Dict, Optional

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from additives import AdditivesAnalyzer
from dish_detector import DishDetector
from product_lookup import ProductLookup
from utils import ProductInfo

app = FastAPI(title="Food Scanner API", version="1.0.0")

# Singletons reused across requests
_lookup = ProductLookup()
_additives = AdditivesAnalyzer()
_dish_detector = DishDetector()


class DishDetectRequest(BaseModel):
    name: Optional[str] = Field(None, description="Dish or product name")
    ingredients_text: str = Field(..., description="Ingredient list or recipe text")
    categories: Optional[str] = Field(None, description="Category hints, comma-separated")


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/product/{barcode}")
async def get_product(barcode: str) -> Dict[str, Any]:
    product = _lookup.get_product(barcode)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return _build_product_response(product)


@app.post("/dish-detect")
async def dish_detect(payload: DishDetectRequest) -> Dict[str, Any]:
    pseudo_product = ProductInfo(
        barcode="manual",
        name=payload.name or "Custom Recipe",
        ingredients_text=payload.ingredients_text,
        categories=payload.categories or "",
    )
    dish = _dish_detector.detect(pseudo_product)

    if not dish:
        return {"match": None, "message": "No confident dish match"}

    return _dish_to_dict(dish)


@app.post("/scan-image")
async def scan_image(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Decode a barcode from an uploaded image and return product info."""
    content = await file.read()
    np_bytes = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(np_bytes, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image data")

    results = _lookup.cache.decoder.decode_image(img) if hasattr(_lookup.cache, "decoder") else None
    # Fallback to on-demand decoder if cache doesn't carry one
    if results is None:
        from barcode_decoder import BarcodeDecoder
        decoder = BarcodeDecoder()
        results = decoder.decode_image(img)

    if not results:
        raise HTTPException(status_code=404, detail="No barcode detected")

    barcode = results[0].data
    product = _lookup.get_product(barcode)
    return {"barcode": barcode, "product": _build_product_response(product)}


@app.get("/search")
async def search_products(q: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    results = _lookup.search_products(q, page=page, page_size=page_size)
    return {"query": q, "count": len(results), "results": results}


def _build_product_response(product: ProductInfo) -> Dict[str, Any]:
    response: Dict[str, Any] = product.to_dict()

    # Additives analysis
    additives = _additives.analyze(product.additives_tags, product.ingredients_text)
    response["additives_analysis"] = {
        "count": len(additives),
        "items": [a.__dict__ for a in additives],
        "summary": _additives.get_summary(additives),
    }

    # Dish detection
    dish = _dish_detector.detect(product)
    response["dish_detection"] = _dish_to_dict(dish) if dish else None

    return response


def _dish_to_dict(dish) -> Dict[str, Any]:
    return {
        "name": dish.profile.name,
        "cuisine": dish.profile.cuisine,
        "description": dish.profile.description,
        "confidence": dish.confidence,
        "matched_keywords": dish.matched_keywords,
        "matched_categories": dish.matched_categories,
        "hero_ingredients": dish.profile.hero_ingredients,
        "recipe_url": dish.profile.recipe_url,
        "serving_style": dish.profile.serving_style,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
