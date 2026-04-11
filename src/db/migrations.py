from src.db.engine import engine
from src.db.models import Base


def create_tables():
    Base.metadata.create_all(bind=engine)
