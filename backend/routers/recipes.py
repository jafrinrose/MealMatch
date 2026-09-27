"""Recipe routes: the collection, photos, saved recipes, ranked suggestions, AI recipes and swaps."""

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ai_services import generate_recipe_from_pantry, select_pantry_for_dish, suggest_ingredient_substitutes
from database import get_db
from models import IngredientRating, Recipe, SavedRecipe, User
from pantry_store import normalize_ingredient_list, pantry_items_for
from preference_store import get_preference_record, preference_lists
from recipe_relevance import (
    choose_pantry_for_request,
    dessert_ingredients_for_savoury,
    ingredients_to_buy,
    lacks_sweetness,
    request_flavour,
    savoury_ingredients_for_dessert,
    title_foods_missing,
    unrelated_pantry_ingredients,
    wants_pantry_only,
)
from recipe_store import (
    browsable_recipes,
    get_recipe_or_404,
    ingredient_similarity,
    recipe_diet_conflicts,
    recipe_from_generated_payload,
    recipe_ingredient_details,
    recipe_is_allergy_safe,
    recipe_is_safe_for_preferences,
    recipe_title_key,
    same_dish,
    serialize_recipe,
)
from recommender import (
    DIET_RULES,
    allergy_conflicts,
    calculate_personalized_score,
    dietary_conflict,
    ingredient_is_match,
    recommendation_sort_key,
    search_recipes,
)
from schemas import GenerateRecipeRequest

router = APIRouter()

# Recipe photos downloaded by the server, kept out of Git.
PHOTO_CACHE = Path(__file__).resolve().parents[1] / ".photo_cache"


@router.get("/recipes")
def get_recipes(user_id: int = 1, db: Session = Depends(get_db)):
    visible_recipes = browsable_recipes(db)
    preferences = get_preference_record(db, user_id)
    visible_recipes = [recipe for recipe in visible_recipes if recipe_is_allergy_safe(recipe, preferences)]
    diet_conflicts = {recipe.id: recipe_diet_conflicts(recipe, preferences) for recipe in visible_recipes}
    familiar_terms = (
        "chicken", "pasta", "lasagna", "taco", "curry", "fried rice", "salmon",
        "pancake", "french toast", "chili", "ramen", "pizza", "burrito", "burger",
        "carbonara", "pad thai", "macaroni", "stir fry", "meatball", "noodle", "soup",
    )
    # Dietary preferences are hard filters with a fallback: recipes that break one
    # come only after every recipe that fits, and say why.
    visible_recipes.sort(key=lambda recipe: (
        bool(diet_conflicts[recipe.id]),
        0 if recipe.source == "TheMealDB" and any(term in recipe.title.lower() for term in familiar_terms) else 1 if recipe.source == "TheMealDB" else 2,
        next((index for index, term in enumerate(familiar_terms) if term in recipe.title.lower()), len(familiar_terms)),
        recipe.title.lower(),
    ))
    return [
        {**serialize_recipe(recipe, db, user_id), "diet_conflicts": diet_conflicts[recipe.id]}
        for recipe in visible_recipes
    ]


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: int, user_id: int = 1, db: Session = Depends(get_db)):
    recipe = get_recipe_or_404(db, recipe_id)

    return serialize_recipe(recipe, db, user_id)


@router.get("/recipes/{recipe_id}/photo")
def recipe_photo(recipe_id: int, db: Session = Depends(get_db)):
    """A recipe's TheMealDB photo, fetched by the server once and then served from disk.

    On some networks Chrome cannot open TheMealDB's image server (its encrypted
    handshake fails with ERR_ECH_FALLBACK_CERTIFICATE_INVALID), so every card
    showed emojis instead of a photo. The cards load photos from here instead.
    """
    url = get_recipe_or_404(db, recipe_id).image_url or ""
    if urlparse(url).scheme not in ("http", "https"):
        raise HTTPException(status_code=404, detail="This recipe has no photo.")

    path = PHOTO_CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}{Path(urlparse(url).path).suffix.lower() or '.jpg'}"
    if not path.exists():
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
        except requests.RequestException as error:
            raise HTTPException(status_code=502, detail="The recipe photo could not be downloaded.") from error
        if not response.headers.get("content-type", "").startswith("image/"):
            raise HTTPException(status_code=502, detail="The recipe photo link did not return an image.")
        PHOTO_CACHE.mkdir(exist_ok=True)
        # Written under a unique name first, so two cards asking at once never see half a file.
        partial = path.with_name(f"{path.name}.{uuid.uuid4().hex}.part")
        partial.write_bytes(response.content)
        partial.replace(path)
    return FileResponse(path, headers={"Cache-Control": "public, max-age=604800"})


@router.post("/saved-recipes/{user_id}/{recipe_id}")
def save_recipe(user_id: int, recipe_id: int, db: Session = Depends(get_db)):
    get_recipe_or_404(db, recipe_id)

    existing = db.query(SavedRecipe).filter(
        SavedRecipe.user_id == user_id,
        SavedRecipe.recipe_id == recipe_id,
    ).first()
    if not existing:
        db.add(SavedRecipe(
            user_id=user_id,
            recipe_id=recipe_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
        db.commit()
    return {"saved": True, "recipe_id": recipe_id}


@router.delete("/saved-recipes/{user_id}/{recipe_id}")
def unsave_recipe(user_id: int, recipe_id: int, db: Session = Depends(get_db)):
    saved = db.query(SavedRecipe).filter(
        SavedRecipe.user_id == user_id,
        SavedRecipe.recipe_id == recipe_id,
    ).first()
    if saved:
        db.delete(saved)
        db.commit()
    return {"saved": False, "recipe_id": recipe_id}


@router.post("/ai-recipes/{user_id}")
def create_ai_recipe(
    user_id: int,
    request: GenerateRecipeRequest,
    db: Session = Depends(get_db),
):
    pantry_items = pantry_items_for(db, user_id)
    if not pantry_items:
        raise HTTPException(status_code=400, detail="Add pantry ingredients before generating a recipe.")

    preferences = get_preference_record(db, user_id)
    saved = preference_lists(preferences)
    dietary, allergies = saved["dietary_restrictions"], saved["allergies"]

    # Offer the model only pantry foods the cook can eat and that belong in the requested dish.
    # Offered a vegan's cheese and eggs, the model used them and every recipe was rejected.
    def can_eat(food: str) -> bool:
        return not dietary_conflict([food], dietary) and not allergy_conflicts([food], allergies)

    reference_recipes = db.query(Recipe).filter(Recipe.source == "TheMealDB").all()
    offered, relevance = choose_pantry_for_request(
        request.request, [item for item in pantry_items if can_eat(item.ingredient)], reference_recipes,
        selector=select_pantry_for_dish,
    )
    pantry_names = [item.ingredient for item in pantry_items]
    avoid = [title.strip() for title in request.avoid_titles if title.strip()]
    # The ideas already shown in this batch, so a repeat can be caught even under a new name.
    shown = db.query(Recipe).filter(Recipe.source == "MealMatch AI", Recipe.title.in_(avoid)).all() if avoid else []
    shown += [Recipe(title=title, ingredients="") for title in avoid if title not in {item.title for item in shown}]
    # What the request settles beyond the dish: its taste and how much shopping it may need.
    flavour = request_flavour(request.request)
    pantry_only = wants_pantry_only(request.request)
    base_request = (
        f"{request.request}. {request.variation}".strip(". ") + ". "
        + ("It must be a sweet dish, such as a dessert, sweet snack or sweet breakfast, with no meat, fish or savoury vegetables. " if flavour == "sweet" else "")
        + ("It must be a savoury dish with no dessert foods such as chocolate, ice cream or syrup. " if flavour == "savoury" else "")
        + ("Build it from the pantry foods listed; add only basic staples such as flour, sugar, butter, oil or spices. " if pantry_only else "")
        + (f"It must be a different dish from: {', '.join(avoid)}. " if avoid else "")
        + "Dietary restrictions (mandatory): "
        + ("; ".join(f"{diet}: {DIET_RULES[diet]}" if diet in DIET_RULES else diet for diet in dietary) or "none") + ". "
        f"Allergies (never use): {', '.join(allergies) or 'none'}."
    )
    active_rules = [*dietary, *[f"{item} allergy" for item in allergies]]
    swaps = [food for food in ("oat milk", "olive oil", "tofu", "chickpeas") if can_eat(food)]
    recipe = None
    safety_score = None
    fallback = None
    correction = ""
    invalid_payloads = 0

    for attempt in range(3):
        try:
            generated = generate_recipe_from_pantry(offered, f"{base_request} {correction}".strip())
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

        if not generated:
            invalid_payloads += 1
            correction = "The previous response was incomplete. Return every required JSON field and at least four detailed steps."
            continue

        candidate = recipe_from_generated_payload(generated)
        if candidate is None:
            invalid_payloads += 1
            correction = "The previous response had invalid ingredients or steps. Return numeric amounts and at least four complete step objects."
            continue

        if len(recipe_ingredient_details(candidate)) < 5 and attempt < 2:
            invalid_payloads += 1
            correction = (
                "The previous recipe listed too few ingredients to be cookable. List every ingredient the dish "
                "needs, including its base, spices, fats and liquids, even if they are not in the pantry."
            )
            continue

        candidate_score = calculate_personalized_score(
            recipe=candidate,
            pantry_items=pantry_items,
            ingredient_ratings={},
            dietary_restrictions=dietary,
            allergies=allergies,
            preferred_cuisines=[],
        )
        candidate_names = [item["name"] for item in recipe_ingredient_details(candidate)]
        if not candidate_score["eligible"]:
            culprits = [name for name in candidate_names if not can_eat(name)]
            correction = (
                f"The previous recipe used {', '.join(culprits) or 'an ingredient'}, which the cook cannot eat "
                f"({', '.join(active_rules)}). Make the recipe again without them, using alternatives that fit"
                + (f" such as {', '.join(swaps)}." if swaps else ".")
            )
            continue

        savoury = savoury_ingredients_for_dessert(request.request, candidate_names)
        if savoury:
            # A dessert with onion or tomato is never kept, not even as a last resort.
            correction = (
                f"The previous recipe put {', '.join(savoury)} in a dessert. Make a proper sweet dish "
                "with only ingredients that belong in a dessert."
            )
            continue

        if lacks_sweetness(request.request, candidate_names):
            correction = (
                f"The previous recipe, \"{candidate.title}\", is not sweet, but the cook asked for something sweet. "
                "Make a dessert or sweet treat built on sweet pantry foods such as fruit, honey or chocolate."
            )
            continue

        dessert_foods = dessert_ingredients_for_savoury(request.request, candidate_names)
        if dessert_foods:
            correction = (
                f"The previous recipe put {', '.join(dessert_foods)} in a savoury dish. "
                "Make a savoury dish with no dessert foods."
            )
            continue

        repeated = next((item for item in shown if same_dish(candidate, item)), None)
        if repeated is not None:
            correction = (
                f"The previous recipe repeated \"{repeated.title}\", which is already one of the ideas. "
                "Give a genuinely different dish with a different title and different main ingredients or method."
            )
            continue

        to_buy = ingredients_to_buy(candidate_names, pantry_names) if pantry_only else []
        if len(to_buy) > 2 and attempt < 2:
            # The cook asked to use what they have: keep it as a last resort and ask for one that shops less.
            fallback = fallback or (candidate, candidate_score)
            correction = (
                f"The cook wants to use what they already have, but the previous recipe needs {', '.join(to_buy)}. "
                "Use the pantry foods listed and only basic staples."
            )
            continue

        unnamed = title_foods_missing(candidate.title, candidate_names, pantry_names)
        if unnamed and attempt < 2:
            fallback = fallback or (candidate, candidate_score)
            correction = (
                f"The previous recipe was called \"{candidate.title}\" but its ingredients leave out {', '.join(unnamed)}. "
                "List every food the title names, or give it a title that matches its ingredients."
            )
            continue

        unrelated = unrelated_pantry_ingredients(candidate_names, offered, relevance, pantry_names)
        if unrelated and attempt < 2:
            # Safe but incoherent: keep it as a last resort and ask for a cleaner dish.
            fallback = fallback or (candidate, candidate_score)
            correction = (
                f"The previous recipe added {', '.join(unrelated)}, which do not belong in this dish. "
                "Leave them out and use only ingredients a chef would put in it."
            )
            continue
        recipe, safety_score = candidate, candidate_score
        break

    if recipe is None and fallback is not None:
        recipe, safety_score = fallback

    if recipe is None or safety_score is None:
        if correction and invalid_payloads < 3:
            detail = (
                "The AI could not produce a recipe that passed MealMatch's checks after three attempts. "
                f"Saved rules: {', '.join(active_rules) or 'none'}. Last check: {correction}"
            )
            raise HTTPException(status_code=422, detail=detail)
        raise HTTPException(status_code=503, detail="The local recipe model did not return a complete recipe after three attempts.")

    # The same dish created by an earlier request is reused, so the collection never
    # shows two cards for one recipe (user testing, round 2).
    existing = next(
        (
            item for item in db.query(Recipe).filter(Recipe.source == "MealMatch AI").all()
            if recipe_title_key(item.title) == recipe_title_key(recipe.title)
            and ingredient_similarity(item.ingredients.split(","), recipe.ingredients.split(",")) >= 0.6
            and recipe_is_safe_for_preferences(item, preferences)
        ),
        None,
    )
    if existing is not None:
        recipe = existing
    else:
        recipe.image_url = ""
        db.add(recipe)
        db.commit()
        db.refresh(recipe)
    result = serialize_recipe(recipe, db, user_id)
    result["score_details"] = safety_score
    result["generation_attempts"] = attempt + 1
    result["pantry_offered"] = offered
    result["preferences_applied"] = {"dietary_restrictions": dietary, "allergies": allergies}
    return result


@router.get("/recommend/{user_id}")
def recommend_recipes(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    pantry_items = pantry_items_for(db, user_id)

    recipes = browsable_recipes(db)

    ratings = (
        db.query(IngredientRating)
        .filter(IngredientRating.user_id == user_id)
        .all()
    )

    user_ingredients = normalize_ingredient_list(
        [item.ingredient for item in pantry_items]
    )

    ingredient_ratings = {
        rating.ingredient.lower(): rating.rating
        for rating in ratings
    }
    semantic_results = search_recipes(
        user_ingredients,
        recipes,
        top_k=min(20, len(recipes)),
    )
    preferences = get_preference_record(db, user_id)
    saved = preference_lists(preferences)
    max_cooking_time = preferences.max_cooking_time if preferences else None
    saved_ids = {
        item.recipe_id
        for item in db.query(SavedRecipe).filter(SavedRecipe.user_id == user_id).all()
    }

    recommendations = []
    semantic_positions = {
        recipe.id: 1 - (index / max(len(semantic_results), 1))
        for index, recipe in enumerate(semantic_results)
    }

    for recipe in recipes:
        score_details = calculate_personalized_score(
            recipe=recipe,
            pantry_items=pantry_items,
            ingredient_ratings=ingredient_ratings,
            dietary_restrictions=saved["dietary_restrictions"],
            allergies=saved["allergies"],
            preferred_cuisines=saved["preferred_cuisines"],
            max_cooking_time=max_cooking_time,
            semantic_score=semantic_positions.get(recipe.id, 0.5 if not semantic_results else 0),
        )

        # Allergy conflicts score 0 and are dropped. Diet conflicts stay, marked,
        # and sort after every recipe that fits the diet.
        if score_details["final_score"] > 0:
            recommendation = serialize_recipe(recipe, db, user_id)
            recommendation["score_details"] = score_details
            recommendation["diet_conflicts"] = score_details["diet_conflicts"]
            recommendation["saved"] = recipe.id in saved_ids
            recommendations.append(recommendation)

    recommendations.sort(key=lambda recipe: recommendation_sort_key(recipe["score_details"]), reverse=True)
    for rank, recommendation in enumerate(recommendations, start=1):
        recommendation["rank"] = rank

    return {
        "user_id": user_id,
        "user_ingredients": user_ingredients,
        "recipe_count": len(recipes),
        "semantic_candidate_count": len(semantic_results),
        "eligible_recipe_count": sum(item["score_details"]["eligible"] for item in recommendations),
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
    }


@router.get("/recipes/{recipe_id}/substitutes/{user_id}")
def recipe_substitutes(recipe_id: int, user_id: int, ingredient: str | None = None, db: Session = Depends(get_db)):
    """Swaps for one ingredient (the one the cook tapped), or for every missing ingredient."""
    recipe = get_recipe_or_404(db, recipe_id)
    pantry_items = pantry_items_for(db, user_id)
    pantry_names = [item.ingredient for item in pantry_items]
    recipe_names = [detail["name"] for detail in recipe_ingredient_details(recipe)]
    missing = [
        name for name in recipe_names
        if not any(ingredient_is_match(name, item) for item in pantry_names)
    ]
    saved = preference_lists(get_preference_record(db, user_id))
    substitutions = suggest_ingredient_substitutes(
        missing_ingredients=[ingredient.strip()] if ingredient and ingredient.strip() else missing,
        pantry_ingredients=pantry_names,
        dietary_restrictions=saved["dietary_restrictions"],
        allergies=saved["allergies"],
        recipe_title=recipe.title or "",
        recipe_ingredients=recipe_names,
    )
    return {"recipe_id": recipe_id, "missing_ingredients": missing, "substitutions": substitutions}
