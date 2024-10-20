import requests
import json
import logging

def get_eval_over_df(search_index, data, ai_request, config): #ai request is request json
    headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {config["openai_api_key"]}'
    }

    

    num_data = len(data)

    for i in range(num_data):
        title = data.loc[i, 'title']
        description = data.loc[i, 'description']

        ai_request["messages"][1]["content"] = title + " " + description
        ai_request["response_format"]["json_schema"]["schema"]["properties"]["filter_1"]["description"] = config["search"]["items"][search_index]["filter"]["filter_1"]
        ai_request["response_format"]["json_schema"]["schema"]["properties"]["filter_2"]["description"] = config["search"]["items"][search_index]["filter"]["filter_2"]
        ai_request["response_format"]["json_schema"]["schema"]["properties"]["filter_3"]["description"] = config["search"]["items"][search_index]["filter"]["filter_3"]
        logging.info("attempting openai eval.")
        try:
            response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            data=json.dumps(ai_request))
            logging.info(f"request successful! {i+1}/{num_data}")
        except Exception as e:
            logging.error(e)

        if response.status_code == 200:
            # Parse the response as JSON
            result = response.json()
        else:
            logging.error(f"Error: {response.status_code}")
            logging.error(response.text)
            continue
        try:
            answer = json.loads(result["choices"][0]["message"]["content"])
            answer["total_value"]
            answer["filter_1"]
            answer["filter_2"]
            answer["filter_3"]
        except Exception as e:
            logging.info(f"error in openai response: {e}")
            continue

        value = answer["total_value"]

        price = data.loc[i, 'price']

        factor = int(value/price * 100) * answer["filter_1"] * answer["filter_2"] * answer["filter_3"]

        data.loc[i, 'total_value'] = value
        data.loc[i, 'value_factor'] = factor
        data.loc[i, 'components'] = str(answer["component_array"])
        data.loc[i, 'component_value'] = str(answer["component_values"])
        data.loc[i, 'parse_status'] = 1

        logging.info("current price: " +  str(price) + ", current value:" + str(value) + ", factor:" + str(factor))

    return data


def search_term_variations(search_index, config, search_request): # search_request in json format
    spez_num = config["search"]["items"][search_index]["search_terms_sepcific_num"]
    gen_num = config["search"]["items"][search_index]["search_terms_general_num"]
    spez = config["search"]["items"][search_index]["search_terms_specific_prompt"]
    gen = config["search"]["items"][search_index]["search_terms_general_prompt"]

    search_term = config["search"]["items"][search_index]["name"]
    headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {config["openai_api_key"]}'
    }

    search_request["messages"][1]["content"] = "the search term is: " + search_term
    search_request["response_format"]["json_schema"]["schema"]["properties"]["general_search_terms"]["description"] = f"this array should be of length {gen_num}. " + gen
    search_request["response_format"]["json_schema"]["schema"]["properties"]["specific_search_terms"]["description"] = f"this array should be of length {spez_num}. " + spez
    logging.info("attempting to generate search terms.")
    try:
        response = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers=headers,
        data=json.dumps(search_request))
        logging.info("openai request successful")
    except Exception as e:
        logging.error(e)

    if response.status_code == 200:
        # Parse the response as JSON
        result = response.json()
        answer = json.loads(result["choices"][0]["message"]["content"])

        gen_list = answer['general_search_terms']
        spez_list = answer["specific_search_terms"]

        main_search_term = config["search"]["items"][search_index]["name"]

        search_term_list = [main_search_term] + gen_list + spez_list

        logging.info("generated search terms: " + str(search_term_list))
        return search_term_list

    else:
        logging.error(f"Error: {response.status_code}")
        logging.error(response.text)
        return []


