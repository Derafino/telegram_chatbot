from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite:///db/database.db")
Session = sessionmaker(engine)
