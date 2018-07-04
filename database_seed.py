import sys
from sqlalchemy import *
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from database_setup import *
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

"""Seed the DB for (super helpful) testing and development"""
engine = create_engine('sqlite:///catalog.db')
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

session.query(Category).delete()
session.query(Item).delete()
session.query(User).delete()

# Create fake user
User1 = User(id=1, name="Devin", email="devinbasinger@gmail.com")
session.add(User1)
session.commit()

# Create categories
Category1 = Category(name="footwear")
session.add(Category1)
session.commit()

Category2 = Category(name="snacks")
session.add(Category2)
session.commit

Category3 = Category(name="tech")
session.add(Category3)
session.commit()

# Populate a category with items for testing
# Using different users for items also
Item1 = Item(title="heels", description="tall footwear", category_id=1, user_id=1)
session.add(Item1)
session.commit()

Item2 = Item(title="popcorn", description="it is popcorn", category_id=2, user_id=1)
session.add(Item2)
session.commit()

Item3 = Item(title="ereader", description="kindle fire", category_id=3, user_id=1)
session.add(Item3)
session.commit()

categories = session.query(Category).all()
for category in categories:
    print "Category: " + category.name

print "Your database has been populated with data!"
