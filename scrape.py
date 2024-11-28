# takes config and prompts and all of the utils to scrape the sites and 

"""
1. load data (pipeline.py)
2. generate search terms (openai.py)
3. scrape to df (tutti.py)
4. analyze listings (openai.py)
5. filter
6. send notifications (pushbullet.py)
7. save data.db (pipeline.py)
"""

import utils.database
import utils.openai
import utils.tutti
import utils.utils
import utils.init
import utils.pushbullet
import json
import logging
from utils.utils import init_logging
from utils.utils import load_config

def scrape():


    config = load_config()
    search_item_num = len(config["search"]["items"])

    for i in range(search_item_num):
        curr_search_item = config["search"]["items"][i]

        with open('config/prompt_search_mini.json', 'r') as file:
            search_request = json.load(file)

        search_terms = utils.openai.search_term_variations(i, config, search_request)

        data = utils.tutti.get_df_from_mult_searches(search_terms, config)


        logging.info("Initiating matching")

        # match after scraped ids and add new ids to scraped table
        scraped_ids = utils.database.load_dataframe_from_sql(config, table_name="scraped")
        data = utils.database.filter_existing_rows(scraped_ids, data)
        scraped_ids = utils.database.append_id_and_plattform(scraped_ids, data)
        utils.database.save_df_to_sql(scraped_ids, config, table_name="scraped")

        with open('config/prompt_value_mini.json', 'r') as file:
            value_request = json.load(file)

        logging.info("Performing analysis on kept data now!")

        data = data[:50]

        data.reset_index(drop=True, inplace=True)
        data = utils.openai.get_eval_over_df(i, data, value_request,config)

        # now we have to do the thresholding and filtering. mayb do the evals on filtered items a couple of times and take average
        logging.info("filtering after analysis...")
        data = utils.database.filter_df(data, config, curr_search_item, i)



        #sending notifications for the offers that passed
        logging.info(f"Sending {len(data)} Notifications!")
        pushbullet_api_key = config["pushbullet_api_key"]
        utils.pushbullet.send_notification_from_df(data, pushbullet_api_key)
        #save-merging dataframe to data.db
        logging.info("Saving valid listings to 'listings' table")
        utils.database.save_df_to_sql(data, config, table_name="listings", if_exists="append")

if __name__ == "__main__":
    init_logging()
    logging.info("")
    logging.info("START OF INSTANCE ################")
    
    try:
        scrape()
    except Exception as e:
        logging.info(e)


