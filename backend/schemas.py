from pydantic import BaseModel, Field


class VerifiedIngredientInput(BaseModel):
    ingredient: str
    quantity: str = ""
    category: str = "other"
    expiry_date: str = ""
    detection_id: str | None = None


class VerifyIngredientsRequest(BaseModel):
    # Old format support: ["chicken", "rice"]
    ingredients: list[str] = []

    # New format support: [{"ingredient": "chicken", "quantity": "2 packs"}]
    items: list[VerifiedIngredientInput] = []
    scan_id: str | None = None
    user_confidence: int | None = Field(default=None, ge=1, le=5)


class UserPreferenceRequest(BaseModel):
    dietary_restrictions: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    disliked_ingredients: list[str] = Field(default_factory=list)
    preferred_cuisines: list[str] = Field(default_factory=list)
    max_cooking_time: int | None = None
    skill_level: str = "beginner"
    onboarding_complete: bool = True


class PantryItemUpdateRequest(BaseModel):
    ingredient: str
    quantity: str = ""
    expiry_date: str = ""
    category: str = "other"


class CookRecipeRequest(BaseModel):
    servings: int = Field(default=1, ge=1, le=12)


class CookingStepRequest(BaseModel):
    current_step: int = Field(default=0, ge=0)


class CookingQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class GenerateRecipeRequest(BaseModel):
    request: str = Field(default="Create an easy meal with what I have", max_length=500)
    # How this option should differ (classic, quicker...). Kept apart from the
    # request so it never influences which pantry foods are considered relevant.
    variation: str = Field(default="", max_length=300)
    avoid_titles: list[str] = Field(default_factory=list, max_length=6)


class ShoppingListRecipeRequest(BaseModel):
    servings: int = Field(default=1, ge=1, le=12)


class GeneralAssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
