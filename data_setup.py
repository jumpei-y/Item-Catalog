from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Category, Base, Item, User

engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Initialize all table
session.query(Category).delete()
session.query(Item).delete()
session.query(User).delete()

# add Category
category1 = Category(name="ROCK")
session.add(category1)
category2 = Category(name="EDM")
session.add(category2)
category3 = Category(name="POP")
session.add(category3)

# add User
user1 = User(email="jumpei_udacity_test666@gmail.com", name="Jumpei")
session.add(user1)

session.commit()
