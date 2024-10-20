######################
# CHECK PACKAGES AND DEPENDENCIES
######################
# pandas, sqalchemy, yaml, openai, pushbullet, numpy,

import subprocess
import sys
import logging
import os
from utils.utils import load_config

# Function to check if a package is installed
def check_and_install_package(package):
    try:
        # Try to import the package to check if it's already installed
        __import__(package)
        logging.info(f"'{package}' is already installed.")
    except ImportError:
        # If not installed, attempt to install it
        logging.info(f"'{package}' not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def check_dependencies(config):
    required_libraries = config["required_libraries"]
    
    # Mapping of import names to pip package names if they differ
    pip_package_mapping = {
        "pushbullet.py": "pushbullet"  # Mapping for pushbullet's pip package name
    }

    # Check and install each library in the list
    for package in required_libraries:
        # Handle cases where pip package names differ from import names
        pip_package_name = pip_package_mapping.get(package, package)
        check_and_install_package(pip_package_name)

    logging.info("All dependencies are installed.")



def initialize_database(config):
    import pandas as pd
    from sqlalchemy import create_engine, inspect
    current_dir = os.getcwd()
    db_relative_path = os.path.join(current_dir, 'data', 'data.db')

    db_dir = os.path.dirname(db_relative_path)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    logging.info(f"Database path set to {db_relative_path}")

    # Define the structure of your empty DataFrame
    columns = ['id', 'plattform', 'item','listing_type', 'title', 'description','category', 'price', 'url', 'image_url', 'search_term', 'components', 'component_value', 'total_value', 'value_factor', 'listing_time', 'scrape_time', 'seller_name', 'postcode', 'location', 'shipping_cost', 'parse_status']
    data_types = {'id':int, 'plattform':'str','item':'str','listing_type':'str', 'title':'str', 'description':'str','category':'str', 'price':'int', 'url':'str', 'image_url':'str', 'search_term':'str', 'components':'str', 'component_value':'str', 'total_value':'int', 'value_factor':'int', 'listing_time':'str', 'scrape_time':'str', 'seller_name':'str', 'postcode':'str', 'location':'str', 'shipping_cost':'float', 'parse_status':'int'}
    df = pd.DataFrame(columns=columns).astype(data_types)

    # Create a SQLAlchemy engine to connect to the SQLite database
    engine = create_engine(f'sqlite:///{db_relative_path}', echo=False)

    # Check if the table 'listings' already exists
    inspector = inspect(engine)
    table_exists = 'listings' in inspector.get_table_names()

    if table_exists:
        logging.info("Table 'listings' already exists. Skipping DataFrame creation.")
    else:
        # Save the empty DataFrame to the SQLite database (table name: 'listings')
        df.to_sql('listings', con=engine, index=False, if_exists='replace')
        logging.info(f"Empty DataFrame saved to {db_relative_path} as 'listings'")

    columns = ["component", "value"]
    data_types = {"component":"str", "value": "int"}
    df = pd.DataFrame(columns=columns).astype(data_types)

    inspector = inspect(engine)
    table_exists = 'components' in inspector.get_table_names()

    if table_exists:
        logging.info("Table 'components' already exists. Skipping DataFrame creation.")
    else:
        df.to_sql('components', con=engine, index=False, if_exists='replace')
        logging.info(f"Empty DataFrame saved to {db_relative_path} as 'components'")

    # Define the structure of your empty DataFrame
    columns = ["id", "plattform"]
    data_types = {'id':int, 'plattform':'str'}
    df = pd.DataFrame(columns=columns).astype(data_types)

    # Create a SQLAlchemy engine to connect to the SQLite database
    engine = create_engine(f'sqlite:///{db_relative_path}', echo=False)

    # Check if the table 'listings' already exists
    inspector = inspect(engine)
    table_exists = 'scraped' in inspector.get_table_names()

    if table_exists:
        logging.info("Table 'scraped' already exists. Skipping DataFrame creation.")
    else:
        # Save the empty DataFrame to the SQLite database (table name: 'listings')
        df.to_sql('scraped', con=engine, index=False, if_exists='replace')
        logging.info(f"Empty DataFrame saved to {db_relative_path} as 'scraped'")

def run_initialization(config):
    check_dependencies(config)
    initialize_database(config)
    logging.info("initialisation succesful!")
