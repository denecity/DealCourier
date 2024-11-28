# at some point i want to add different plattforms. this library includes utils that
# scrapes tutti.ch and updates/creates a unified data.db in the data directory.
# the end goal is to have a df of the shape of data.db
import requests
import logging
import re
import json
import pandas as pd

def get_html_content(url):
    request_tries = 0
    while request_tries < 200:
        try:
            # Send a GET request to the specified URL
            response = requests.get(url)
            
            # Check if the request was successful
            if response.status_code == 200:
                logging.info("Successfully retrieved HTML content.")
                return response.text
            else:
                logging.info(f"Failed to retrieve content. Status code: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logging.info(f"An error occurred: {e}")
            request_tries += 1
    logging.info("Something is wront with the requesting or internet connection. Skipping")
    return None

def get_df_from_search_term(search_term, main_search_term):
    search_item = search_term.replace(" ", "%20")
    url = "https://www.tutti.ch/de/q/suche?query="+search_item+"&lang=de"

    html_content = get_html_content(url)
    json_pattern = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL)
    json_match = json_pattern.search(html_content)

    # Save the extracted JSON string to a proper JSON file
    json_string = json_match.group(1)

    # Convert the string to a dictionary
    json_data = json.loads(json_string)

    edges = json_data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]["listings"]["edges"]

    # generate the dataframe
    data = create_dataframe_from_search_result(edges, search_term, main_search_term)

    return data

def create_dataframe_from_search_result(json_input_edges, search_term, main_search_term):
    #json_data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]["listings"]["edges"][i]
    num_results = len(json_input_edges)

    columns = ['id', 'plattform','item', 'listing_type', 'title', 'description','category', 'price', 'url', 'image_url', 'search_term', 'components', 'component_value', 'total_value', 'value_factor', 'listing_time', 'scrape_time', 'seller_name', 'postcode', 'location', 'shipping_cost', 'parse_status']
    data_types = {'id':int, 'plattform':'str','item':'str','listing_type':'str', 'title':'str', 'description':'str','category':'str', 'price':'int', 'url':'str', 'image_url':'str', 'search_term':'str', 'components':'str', 'component_value':'str', 'total_value':'int', 'value_factor':'int', 'listing_time':'str', 'scrape_time':'str', 'seller_name':'str', 'postcode':'str', 'location':'str', 'shipping_cost':'float', 'parse_status':'int'}
    data = pd.DataFrame(columns=columns).astype(data_types)

    if num_results > 0:
        for i in range(num_results):
            data = append_to_dataframe(json_input_edges[i], data, search_term, main_search_term)
    
    return data


def append_to_dataframe(json_input, existing_df, search_term, main_search_term):
    # Extracting the relevant fields from the JSON structure
    node = json_input.get('node', {})

    try:
        thumbnail = node["thumbnail"]["normalRendition"]["src"]
    except:
        thumbnail = ""

    
    # Creating a flat dictionary from the nested structure
    data = {
        'listingID': node.get('listingID'),
        'title': node.get('title'),
        'body': node.get('body'),
        'postcode': node.get('postcodeInformation', {}).get('postcode'),
        'locationName': node.get('postcodeInformation', {}).get('locationName'),
        'canton_shortName': node.get('postcodeInformation', {}).get('canton', {}).get('shortName'),
        'canton_name': node.get('postcodeInformation', {}).get('canton', {}).get('name'),
        'timestamp': node.get('timestamp'),
        'formattedPrice': node.get('formattedPrice'),
        'highlighted': node.get('highlighted'),
        'primaryCategoryID': node.get('primaryCategory', {}).get('categoryID'),
        'sellerAlias': node.get('sellerInfo', {}).get('alias'),
        'seo_deSlug': node.get('seoInformation', {}).get('deSlug'),
        'seo_frSlug': node.get('seoInformation', {}).get('frSlug'),
        'seo_itSlug': node.get('seoInformation', {}).get('itSlug'),
        'image_url': thumbnail,
        'timestamp': node.get('timestamp'),
        'seller_name': node.get('sellerInfo', {}).get('alias')
    }

    id = data["listingID"]
    plattform = "tutti"
    item = main_search_term
    listing_type = "offer"
    title = data["title"]
    description = data["body"]
    category = data["primaryCategoryID"]
    price = extract_price(data["formattedPrice"])
    if price == None:
        logging.info("found free offer. Skipping...")
        return existing_df
    
    url = "https://www.tutti.ch/de/vi/" + data["seo_deSlug"] +"/"+ data["listingID"]
    image_url = data["image_url"]
    components = None # those will be filled in the openai phase
    component_value = None
    total_value = None
    value_factor = None
    listing_time = data["timestamp"]
    scrape_time = None
    seller_name = data["seller_name"]
    postcode = data["postcode"]
    location = data["locationName"]
    shipping_cost = 0
    parse_status = 0

    new_row = pd.DataFrame([{
        "id" : id,
        "plattform" : plattform,
        "item" : item,
        "listing_type" : listing_type,
        "title" : title,
        "description" : description,
        "category" : category,
        "price" : price,
        "url" : url,
        "image_url" : image_url,
        "search_term" : search_term,
        "components" : components,
        "component_value" : component_value,
        "total_value" : total_value,
        "value_factor" : value_factor,
        "listing_time" : listing_time,
        "scrape_time" : scrape_time,
        "seller_name" : seller_name,
        "postcode" : postcode,
        "location" : location,
        "shipping_cost" : shipping_cost,
        "parse_status" : parse_status
    }])
    
    # Append the new row to the existing DataFrame
    updated_df = pd.concat([existing_df, new_row], ignore_index=True)
    return updated_df

def extract_price(value):
    # Remove apostrophes used as thousands separators
    value = value.replace("'", "")
    # Use regex to match the format "number.-"
    match = re.match(r'^(\d+)\.-$', value)
    if match:
        return int(match.group(1))
    else:
        return None
    
def get_df_from_mult_searches(search_items_list, config):

    main_search_term = search_items_list[0]

    logging.info("merging data from search terms: " +  str(search_items_list))

    columns = ['id', 'plattform','item', 'listing_type', 'title', 'description','category', 'price', 'url', 'image_url', 'search_term', 'components', 'component_value', 'total_value', 'value_factor', 'listing_time', 'scrape_time', 'seller_name', 'postcode', 'location', 'shipping_cost', 'parse_status']
    data_types = {'id':int, 'plattform':'str','item':'str','listing_type':'str', 'title':'str', 'description':'str','category':'str', 'price':'int', 'url':'str', 'image_url':'str', 'search_term':'str', 'components':'str', 'component_value':'str', 'total_value':'int', 'value_factor':'int', 'listing_time':'str', 'scrape_time':'str', 'seller_name':'str', 'postcode':'str', 'location':'str', 'shipping_cost':'float', 'parse_status':'int'}
    data = pd.DataFrame(columns=columns).astype(data_types)

    num_items_1 = 0 # just for logging
    num_items_2 = 0
    num_items_new = 0

    num_search_terms = len(search_items_list)
    

    for i in range(num_search_terms):
        try:
            new_data = get_df_from_search_term(search_items_list[i], main_search_term)
            num_items_2 = len(new_data)
            combined_data = pd.concat([data, new_data], ignore_index=True)
            data = combined_data.drop_duplicates(subset="id", keep='first')
            num_items_new = len(data)
        except:
            logging.info("skipping " + str(search_items_list[i]))

        logging.info("merged: " +  str(i) + " out of " + str(num_search_terms))
        logging.info("search results merged:" +  str(search_items_list[i]))
        logging.info(str(num_items_new) +  " out of " +  str(num_items_1 + num_items_2) +  " entries kept!")
        logging.info(str(num_items_new - num_items_1) +  " added, " + str(num_items_1 + num_items_2 - num_items_new) + " thrown out!")
        try:
            num_items_1 = len(data)
        except: ""

    return data