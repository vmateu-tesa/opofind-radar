import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'oporadar.db')

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_session():
    return SessionLocal()
