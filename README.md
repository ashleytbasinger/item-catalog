# Overview
Inventory/Item Catalog 

# Components
- HTML structure assisted by Bootstrap
- Templates and routes created with Flask
- Utilizes SQLAlchemy to contact the database
- RESTful API endpoints return .json files
- Google authenticates users (only authenticated users can create/edit inventory items)

# To run the application:
- Install the dependency libraries: execute `pip install -r requirements.txt`
- Setup the database: `python database_setup.py`
- Seed the database with sample data: `python database_seed.py`
- Execute `python project.py`
