from database import Base, engine, SessionLocal
from models import User, Recipe, IngredientRating

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

user = User(
    name="Demo User",
)
db.add(user)
db.commit()

recipes = [
    Recipe(
        title="Chicken Rice Bowl",
        ingredients="chicken,rice,spinach,soy sauce,garlic",
        instructions="Cook rice. Stir-fry chicken with garlic. Add spinach. Serve together.",
        cooking_time=25,
        difficulty="Beginner",
        cuisine="Asian",
        calories=520
    ),
    Recipe(
        title="Tomato Cheese Pasta",
        ingredients="pasta,tomato,cheese,garlic,olive oil",
        instructions="Boil pasta. Cook tomato with garlic. Mix pasta and top with cheese.",
        cooking_time=20,
        difficulty="Beginner",
        cuisine="Italian",
        calories=480
    ),
    Recipe(
        title="Vegetable Fried Rice",
        ingredients="rice,egg,carrot,peas,soy sauce,onion",
        instructions="Scramble egg. Add vegetables and rice. Stir-fry with soy sauce.",
        cooking_time=18,
        difficulty="Beginner",
        cuisine="Asian",
        calories=430
    ),
    Recipe(
        title="Spinach Omelette",
        ingredients="egg,spinach,cheese,onion,butter",
        instructions="Beat eggs. Cook onion and spinach. Add eggs and cheese. Fold and serve.",
        cooking_time=12,
        difficulty="Beginner",
        cuisine="Western",
        calories=350
    ),
    Recipe(
        title="Garlic Tomato Rice",
        ingredients="rice,tomato,garlic,onion,olive oil",
        instructions="Cook garlic and onion. Add tomato and rice. Mix well and serve warm.",
        cooking_time=22,
        difficulty="Beginner",
        cuisine="Fusion",
        calories=410
    ),
    Recipe(
        title="Berry Yogurt Granola Bowl",
        ingredients="yogurt,berries,granola,honey,oats",
        instructions="Add yogurt to a bowl. Top with berries, granola, oats, and honey.",
        cooking_time=5,
        difficulty="Beginner",
        cuisine="Breakfast",
        calories=320
    ),
    Recipe(
        title="Overnight Oats with Berries",
        ingredients="oats,yogurt,berries,milk,honey",
        instructions="Mix oats, yogurt, milk, and honey. Refrigerate overnight. Top with berries before eating.",
        cooking_time=10,
        difficulty="Beginner",
        cuisine="Breakfast",
        calories=360
    ),
    Recipe(
        title="Granola Berry Parfait",
        ingredients="granola,yogurt,berries,banana,honey",
        instructions="Layer yogurt, granola, berries, banana, and honey in a glass or bowl.",
        cooking_time=5,
        difficulty="Beginner",
        cuisine="Breakfast",
        calories=300
    ),
    Recipe(
        title="Berry Oat Smoothie",
        ingredients="berries,oats,yogurt,milk,banana",
        instructions="Blend berries, oats, yogurt, milk, and banana until smooth.",
        cooking_time=5,
        difficulty="Beginner",
        cuisine="Breakfast",
        calories=280,
    ),
    Recipe(
        title="Spinach Tomato Cucumber Salad",
        ingredients="spinach,tomato,cucumber,olive oil,salt,pepper,feta",
        instructions="Slice cucumber and tomato. Toss with spinach, feta, olive oil, salt, and pepper.",
        cooking_time=10,
        difficulty="Beginner",
        cuisine="Mediterranean",
        calories=250,
    ),
    Recipe(
        title="Creamy Cabbage and Potato Soup",
        ingredients="cabbage,potato,milk,cream,onion,garlic,salt,pepper",
        instructions="Boil potatoes with cabbage, onion, and garlic. Add milk and cream, then simmer until thick and warm.",
        cooking_time=30,
        difficulty="Beginner",
        cuisine="Comfort Food",
        calories=380,
    ),
    Recipe(
        title="Chicken Thighs with Sweet Pepper and Tomato",
        ingredients="chicken thigh,sweet pepper,tomato,onion,garlic,olive oil,salt,pepper",
        instructions="Season chicken thighs. Cook with sweet pepper, tomato, onion, garlic, and olive oil until the chicken is cooked through.",
        cooking_time=35,
        difficulty="Intermediate",
        cuisine="Home Cooking",
        calories=520,
    ),
    Recipe(
        title="Shrimp Tomato Pepper Stir Fry",
        ingredients="shrimp,tomato,sweet pepper,garlic,olive oil,rice,noodles",
        instructions="Cook shrimp with garlic, tomato, and sweet pepper. Serve with rice or noodles.",
        cooking_time=20,
        difficulty="Beginner",
        cuisine="Asian Fusion",
        calories=430,
    ),
    Recipe(
        title="Avocado Feta Tomato Toast",
        ingredients="avocado,feta,tomato,bread,olive oil,pepper",
        instructions="Toast bread. Mash avocado on top, then add feta, tomato, olive oil, and pepper.",
        cooking_time=10,
        difficulty="Beginner",
        cuisine="Cafe Style",
        calories=350,
    ),
    Recipe(
        title="Brie and Strawberry Baguette",
        ingredients="brie,strawberry,bread,baguette,honey",
        instructions="Slice baguette and add brie. Top with strawberries and a little honey.",
        cooking_time=10,
        difficulty="Beginner",
        cuisine="Snack",
        calories=300,
    ),
    Recipe(
        title="Greek Feta Cucumber Tomato Bowl",
        ingredients="feta,cucumber,tomato,olives,olive oil,pepper,bread",
        instructions="Combine feta, cucumber, tomato, and olives. Drizzle with olive oil and serve with bread.",
        cooking_time=10,
        difficulty="Beginner",
        cuisine="Greek",
        calories=360,
    ),
    Recipe(
        title="Potato Wedges with Coleslaw",
        ingredients="potato,cabbage,carrot,mayonnaise,salt,pepper",
        instructions="Bake potato wedges until crispy. Mix cabbage and carrot with mayonnaise, salt, and pepper to make coleslaw.",
        cooking_time=35,
        difficulty="Beginner",
        cuisine="American",
        calories=450,
    ),
    Recipe(
        title="Cheesy Bread with Tomato Dip",
        ingredients="bread,cheese,tomato,garlic,olive oil,salt",
        instructions="Toast bread with cheese. Cook tomato with garlic and olive oil to make a quick dip.",
        cooking_time=15,
        difficulty="Beginner",
        cuisine="Snack",
        calories=390,
    ),
    Recipe(
        title="Banana Yogurt Cereal Cup",
        ingredients="banana,yogurt,cereal,milk,honey",
        instructions="Layer yogurt, sliced banana, cereal, and a splash of milk in a cup or bowl.",
        cooking_time=5,
        difficulty="Beginner",
        cuisine="Breakfast",
        calories=310,
    ),
    Recipe(
        title="Chicken Pickle Cheese Sandwich",
        ingredients="chicken,pickles,cheese,bread,butter",
        instructions="Layer cooked chicken, pickles, and cheese between bread slices. Toast with butter until golden.",
        cooking_time=15,
        difficulty="Beginner",
        cuisine="Sandwich",
        calories=500,
    ),
    Recipe(
        title="Eggplant Chicken Bake",
        ingredients="eggplant,chicken,tomato,cheese,onion,garlic,olive oil",
        instructions="Layer eggplant, chicken, tomato, onion, and cheese. Bake until golden and cooked through.",
        cooking_time=40,
        difficulty="Intermediate",
        cuisine="Baked Meal",
        calories=560,
    ),
    Recipe(
        title="Green Onion Tomato Omelette",
        ingredients="egg,green onion,tomato,cheese,milk,salt,pepper",
        instructions="Whisk eggs with milk. Add green onion, tomato, and cheese. Cook in a pan until set.",
        cooking_time=12,
        difficulty="Beginner",
        cuisine="Breakfast",
        calories=330,
    ),
    Recipe(
        title="Peanut Yogurt Fruit Bowl",
        ingredients="peanuts,yogurt,strawberry,banana,honey,cereal",
        instructions="Add yogurt to a bowl. Top with peanuts, fruit, cereal, and honey.",
        cooking_time=5,
        difficulty="Beginner",
        cuisine="Breakfast",
        calories=400,
    ),
    Recipe(
        title="Tomato Feta Potato Skillet",
        ingredients="potato,tomato,feta,onion,olive oil,pepper",
        instructions="Pan-fry potatoes with onion and tomato. Crumble feta over the top before serving.",
        cooking_time=25,
        difficulty="Beginner",
        cuisine="Mediterranean",
        calories=420,
    ),
    Recipe(
        title="Cucumber Yogurt Dip with Bread",
        ingredients="cucumber,yogurt,garlic,bread,salt,pepper",
        instructions="Mix grated cucumber with yogurt, garlic, salt, and pepper. Serve with bread.",
        cooking_time=10,
        difficulty="Beginner",
        cuisine="Mediterranean",
        calories=260,
    ),
    Recipe(
        title="Shrimp Avocado Tomato Salad",
        ingredients="shrimp,avocado,tomato,cucumber,olive oil,lemon,pepper",
        instructions="Cook shrimp, then toss with avocado, tomato, cucumber, olive oil, lemon, and pepper.",
        cooking_time=20,
        difficulty="Beginner",
        cuisine="Fresh Bowl",
        calories=430,
    ),
]


for recipe in recipes:
    db.add(recipe)

ratings = [
    IngredientRating(user_id=1, ingredient="chicken", rating=2),
    IngredientRating(user_id=1, ingredient="spinach", rating=1),
    IngredientRating(user_id=1, ingredient="cheese", rating=1),
    IngredientRating(user_id=1, ingredient="mushroom", rating=-2),
]

for rating in ratings:
    db.add(rating)

db.commit()
db.close()

print("Database seeded successfully.")
