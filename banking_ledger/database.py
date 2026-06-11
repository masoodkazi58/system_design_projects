from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase,sessionmaker
from dotenv import load_dotenv
import os

database_url = "DATABASE_URL"
load_dotenv()
engine = create_engine(
    url=os.getenv(database_url),
    echo=True
)

Sessionlocal = sessionmaker(autoflush=False,autocommit=False,bind=engine)



class Base(DeclarativeBase):
    pass

def get_db():
    db = Sessionlocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
