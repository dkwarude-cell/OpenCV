"""Dish detection support built on top of curated recipe profiles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from utils import ProductInfo, logger

DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "dish_profiles.json"


def _normalize_text(value: str) -> str:
    """Lowercase and strip punctuation so keyword matching stays predictable."""
    if not value:
        return ""
    normalized = re.sub(r"[^a-z0-9\s]", " ", value.lower())
    return re.sub(r"\s+", " ", normalized).strip()


@dataclass
class DishProfile:
    """Serialized representation of a dish/recipe signature."""

    name: str
    cuisine: str
    description: str
    ingredient_keywords: List[str] = field(default_factory=list)
    required_terms: List[str] = field(default_factory=list)
    category_keywords: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    hero_ingredients: List[str] = field(default_factory=list)
    recipe_url: Optional[str] = None
    serving_style: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: dict) -> "DishProfile":
        return cls(
            name=payload.get("name", "Unnamed Dish"),
            cuisine=payload.get("cuisine", "Global"),
            description=payload.get("description", ""),
            ingredient_keywords=[kw.lower() for kw in payload.get("ingredient_keywords", [])],
            required_terms=[kw.lower() for kw in payload.get("required_terms", [])],
            category_keywords=[kw.lower() for kw in payload.get("category_keywords", [])],
            aliases=[kw.lower() for kw in payload.get("aliases", [])],
            hero_ingredients=[kw.lower() for kw in payload.get("hero_ingredients", [])],
            recipe_url=payload.get("recipe_url"),
            serving_style=payload.get("serving_style"),
        )


@dataclass
class DetectedDish:
    """Result returned by the detector when a product matches a profile."""

    profile: DishProfile
    confidence: float
    matched_keywords: List[str] = field(default_factory=list)
    matched_categories: List[str] = field(default_factory=list)
    reason: str = ""


class DishDetector:
    """Simple rule-based dish detector backed by metadata JSON."""

    def __init__(self, dataset_path: Optional[Path] = None, min_confidence: float = 0.35):
        self.dataset_path = Path(dataset_path) if dataset_path else DATASET_PATH
        self.min_confidence = min_confidence
        self._profiles: List[DishProfile] = []
        self._load_profiles()

    def _load_profiles(self) -> None:
        if not self.dataset_path.exists():
            logger.warning("Dish dataset not found at %s", self.dataset_path)
            self._profiles = []
            return

        try:
            with self.dataset_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load dish dataset: %s", exc)
            self._profiles = []
            return

        self._profiles = [DishProfile.from_dict(item) for item in payload]
        logger.debug("Loaded %s dish profiles", len(self._profiles))

    def detect(self, product: ProductInfo) -> Optional[DetectedDish]:
        """Attempt to match the provided product to a known dish profile."""
        combined_text = " ".join(
            part for part in [product.name, product.ingredients_text, product.categories]
            if part
        )
        normalized_text = _normalize_text(combined_text)

        if not normalized_text:
            return None

        best_match: Optional[DetectedDish] = None

        for profile in self._profiles:
            candidate = self._score_profile(profile, normalized_text)
            if candidate and (best_match is None or candidate.confidence > best_match.confidence):
                best_match = candidate

        if best_match and best_match.confidence >= self.min_confidence:
            return best_match
        return None

    def _score_profile(self, profile: DishProfile, normalized_text: str) -> Optional[DetectedDish]:
        """Score how well the normalized product text aligns with the profile."""
        keyword_hits = [kw for kw in profile.ingredient_keywords if kw in normalized_text]
        if not keyword_hits:
            return None

        if profile.required_terms and not any(term in normalized_text for term in profile.required_terms):
            return None

        score = len(keyword_hits) / max(1, len(profile.ingredient_keywords))
        alias_hits = [alias for alias in profile.aliases if alias in normalized_text]
        category_hits = [cat for cat in profile.category_keywords if cat in normalized_text]
        hero_hits = [hero for hero in profile.hero_ingredients if hero in normalized_text]

        if alias_hits:
            score += 0.15
        if category_hits:
            score += 0.1
        if hero_hits:
            score += 0.05 * len(hero_hits)

        score = min(score, 1.0)

        reason = "Matched keywords"
        if alias_hits:
            reason += ", alias"
        if category_hits:
            reason += ", category"
        if hero_hits:
            reason += ", hero ingredient"

        return DetectedDish(
            profile=profile,
            confidence=round(score, 2),
            matched_keywords=sorted(set(keyword_hits + hero_hits + alias_hits)),
            matched_categories=category_hits,
            reason=reason,
        )