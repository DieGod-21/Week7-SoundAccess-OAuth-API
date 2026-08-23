"""Create all tables and seed development data.

Usage:  python -m scripts.init_db   (run from the project root, .env present)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, engine, SessionLocal  # noqa: E402
from app import models  # noqa: F401,E402  (register models)
from app.seed import seed  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = seed(db)
    finally:
        db.close()
    print(f"Database ready: {result}")


if __name__ == "__main__":
    main()
