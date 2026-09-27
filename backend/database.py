import os
import shutil
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "mealmatch.db"
# The demo user and the recipe collection, with no pantry, cooking or study
# data. The working database is kept out of Git because it holds that data.
STARTER_DATABASE_PATH = DATABASE_PATH.with_name("mealmatch_starter.db")
DATABASE_URL = os.getenv("MEALMATCH_DATABASE_URL", f"sqlite:///{DATABASE_PATH}")

if "MEALMATCH_DATABASE_URL" not in os.environ and not DATABASE_PATH.exists():
    shutil.copyfile(STARTER_DATABASE_PATH, DATABASE_PATH)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
