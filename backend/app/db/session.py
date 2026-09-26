from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://sentryops:sentryops@postgres:5432/sentryops')
# For local testing if postgres host is not resolvable, use localhost:
# DATABASE_URL = 'postgresql+psycopg2://sentryops:sentryops@localhost:5432/sentryops'

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
