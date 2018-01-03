# coding: utf-8

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer

DB_URL = 'sqlite:///./data/game.db'
engine = create_engine(DB_URL, convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


class Question(Base):
    __tablename__ = 'questions'

    quiz = Column(String(2000), primary_key=True)
    school = Column(String(20), nullable=False)
    type = Column(String(20), nullable=False)    
    options = Column(String(2000), nullable=False)
    answer = Column(String(2000), nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == '__main__':
    init_db()
