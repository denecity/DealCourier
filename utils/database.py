# this handles everything that has to do
from sqlalchemy import create_engine
import pandas as pd
import logging
import os


def load_dataframe_from_sql(config, table_name="listings"):
    # Create an SQLite engine
    database_path = config["database_path"]
    database_path = os.path.join(os.getcwd(), database_path)
    engine = create_engine(f'sqlite:///{database_path}')
    
    # Load the SQL table into a DataFrame
    df = pd.read_sql_table(table_name, con=engine)

    logging.info(f"DataFrame loaded from table '{table_name}' in database '{database_path}'.")
    return df


def filter_df(data, config, curr_search_item, curr_search_index):

    minimum_value_factor = config["search"]["items"][curr_search_index]["threshold"]["minimum_value_factor"]
    minimum_price = config["search"]["items"][curr_search_index]["threshold"]["minimum_price"]
    minimum_profit = config["search"]["items"][curr_search_index]["threshold"]["minimum_profit"]
    maximum_price = config["search"]["items"][curr_search_index]["threshold"]["maximum_price"]

    for i in range(len(data)):
        try:
            curr_price = data.loc[i, "price"]
            curr_value = data.loc[i, "total_value"]
            curr_value_factor = data.loc[i, "value_factor"]

            curr_offer_name = data.loc[i, "title"]

            curr_profit = curr_value - curr_price

            gate = 1 # 1 means value is getting kept

            reason = ""

            if curr_price < minimum_price:
                gate *= 0
                reason = reason + " its price was too low"
            
            if maximum_price < curr_price:
                gate *= 0
                reason = reason + " its price was too high"

            if curr_value_factor < minimum_value_factor:
                gate *= 0
                reason = reason + ", its value factor was too low"

            if curr_profit < minimum_profit:
                gate *= 0
                reason = reason + ", its profit was too low"

            if not gate:
                data = data.drop(i, inplace=False)
                logging.info(f"The offer {curr_offer_name} ({curr_search_index}) with price:{curr_price}, profit: {curr_profit}, value: {curr_value}, factor:{curr_value_factor} did not pass the filter and is getting dropped!")
                logging.info(f"Reason:" + reason)
            else:
                logging.info(f"The offer {curr_offer_name} ({curr_search_index}) with price:{curr_price}, profit: {curr_profit}, value: {curr_value}, factor:{curr_value_factor} was accepted")
        except Exception as e:
            logging.info("The offer could not be parsed. dropping")
            data = data.drop(i, inplace=False)
            
    data = data.reset_index(drop=True, inplace=False)
    return data


def filter_existing_rows(total_data, curr_data):
    start_len = len(curr_data)

    # Ensure the 'id' is treated as a string for both dataframes when creating the composite key
    total_data['composite_key'] = total_data['id'].astype(str) + "_" + total_data['plattform']
    curr_data['composite_key'] = curr_data['id'].astype(str) + "_" + curr_data['plattform']

    # Filter out rows from curr_data where the composite key exists in total_data
    filtered_curr_data = curr_data[~curr_data['composite_key'].isin(total_data['composite_key'])]

    # Drop the composite_key column from the result
    filtered_curr_data = filtered_curr_data.drop(columns=['composite_key'])
    end_len = len(filtered_curr_data)

    logging.info(f"filtered scraped data on database. Threw out {start_len-end_len} datapoints. Kept {end_len}")

    filtered_curr_data = filtered_curr_data.reset_index(drop=True, inplace=False)
    return filtered_curr_data

def append_id_and_plattform(total_data, curr_data):
    # Extract the "id" and "plattform" columns from curr_data
    curr_data_subset = curr_data[['id', 'plattform']]

    # Ensure there are no duplicates in curr_data_subset
    curr_data_subset = curr_data_subset.drop_duplicates()

    # Concatenate total_data and curr_data_subset and drop duplicates to keep only unique rows
    updated_total_data = pd.concat([total_data, curr_data_subset], ignore_index=True).drop_duplicates()

    logging.info(f"Added {len(updated_total_data) - len(total_data)} new entries to the 'scraped' table")

    return updated_total_data

def save_df_to_sql(data, config, table_name, if_exists="replace"):

    database_path = config["database_path"]

    # Create an SQLite engine
    engine = create_engine(f'sqlite:///{database_path}')
    
    # Save the DataFrame to the SQL table
    if len(data) > 0:
        data.to_sql(table_name, con=engine, if_exists=if_exists, index=False)
        logging.info(f"DataFrame saved to table '{table_name}' in database '{database_path}'.")
        return
    else:
        logging.info("No entries to log. Ending database link.")
        return
