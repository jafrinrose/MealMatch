from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, inspect, text
from database import Base, engine

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )

    dietary_restrictions = Column(
        String,
        default="",
    )

    allergies = Column(
        String,
        default="",
    )

    disliked_ingredients = Column(
        String,
        default="",
    )

    preferred_cuisines = Column(
        String,
        default="",
    )

    max_cooking_time = Column(
        Integer,
        nullable=True,
    )

    skill_level = Column(
        String,
        default="beginner",
    )

    onboarding_complete = Column(
        Boolean,
        default=False,
    )

class PantryItem(Base):
    __tablename__ = "pantry_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    ingredient = Column(String)
    quantity = Column(String, default="")
    expiry_date = Column(String, default="")
    expiry_estimated = Column(Boolean, default=False)
    category = Column(String, default="other")

class IngredientRating(Base):
    __tablename__ = "ingredient_ratings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    ingredient = Column(String)
    rating = Column(Integer)

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    ingredients = Column(Text)
    instructions = Column(Text)
    cooking_time = Column(Integer)
    difficulty = Column(String)
    cuisine = Column(String)
    calories = Column(Integer)
    prep_time = Column(Integer, default=10)
    servings = Column(Integer, default=2)
    image_url = Column(String, default="")
    source = Column(String, default="MealMatch")
    source_id = Column(String, default="")
    ingredient_details = Column(Text, default="")
    step_details = Column(Text, default="")

class SavedRecipe(Base):
    __tablename__ = "saved_recipes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    recipe_id = Column(Integer)
    rating = Column(Integer, default=0)
    created_at = Column(String, default="")


class CookingSession(Base):
    __tablename__ = "cooking_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False)
    servings = Column(Integer, default=1)
    started_at = Column(String, nullable=False)
    ready_at = Column(String, nullable=False)
    status = Column(String, default="active")
    current_step = Column(Integer, default=0)
    pantry_snapshot = Column(Text, default="[]")


class CookingMessage(Base):
    __tablename__ = "cooking_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("cooking_sessions.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)


class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=True)
    ingredient = Column(String, nullable=False)
    quantity = Column(String, default="")
    checked = Column(Boolean, default=False)
    created_at = Column(String, nullable=False)


class VisionScan(Base):
    """Privacy-preserving photo-detection and confirmation study record."""

    __tablename__ = "vision_scans"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source = Column(String, default="photo")
    # Kept as separate fields so historical detector-assisted scans remain
    # interpretable after the production pipeline moved to Qwen-only vision.
    detector_model = Column(String, default="")
    semantic_model = Column(String, default="Qwen2.5-VL")
    status = Column(String, default="analysing")
    created_at = Column(String, nullable=False)
    analysis_completed_at = Column(String, default="")
    confirmed_at = Column(String, default="")
    # Upload to first suggestions (the whole-photo pass); total includes the close-ups.
    inference_ms = Column(Integer, default=0)
    total_analysis_ms = Column(Integer, default=0)
    confirmation_ms = Column(Integer, default=0)
    initial_detections = Column(Text, default="[]")
    final_items = Column(Text, default="[]")
    initial_count = Column(Integer, default=0)
    final_count = Column(Integer, default=0)
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    renames = Column(Integer, default=0)
    user_confidence = Column(Integer, nullable=True)
    failure_reason = Column(Text, default="")
    warnings = Column(Text, default="[]")
    pass_log = Column(Text, default="[]")


# Columns added after the first version, so older local databases keep working.
ADDED_COLUMNS = [
    ("pantry_items", "category", "VARCHAR DEFAULT 'other'"),
    ("pantry_items", "expiry_estimated", "BOOLEAN DEFAULT 0"),
    ("recipes", "prep_time", "INTEGER DEFAULT 10"),
    ("recipes", "servings", "INTEGER DEFAULT 2"),
    ("recipes", "image_url", "VARCHAR DEFAULT ''"),
    ("recipes", "source", "VARCHAR DEFAULT 'MealMatch'"),
    ("recipes", "source_id", "VARCHAR DEFAULT ''"),
    ("recipes", "ingredient_details", "TEXT DEFAULT ''"),
    ("recipes", "step_details", "TEXT DEFAULT ''"),
    ("saved_recipes", "created_at", "VARCHAR DEFAULT ''"),
    ("vision_scans", "pass_log", "TEXT DEFAULT '[]'"),
    ("vision_scans", "total_analysis_ms", "INTEGER DEFAULT 0"),
]


def upgrade_database() -> None:
    """Create any missing tables and add the columns an older database lacks."""
    Base.metadata.create_all(bind=engine)
    for table_name, column_name, definition in ADDED_COLUMNS:
        columns = {column["name"] for column in inspect(engine).get_columns(table_name)}
        if column_name not in columns:
            with engine.begin() as connection:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))
