import yaml
import os
import logging


# CONFIG LOADING PART

# Global variable to store config
def load_config(config_file='config/config.yaml'):
    #Load the configuration from the YAML file located in the config directory.
    global CONFIG
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', config_file)
    with open(config_path, 'r') as file:
        CONFIG = yaml.safe_load(file)
    logging.debug(f"{config_file} successfully loaded.")
    return CONFIG



# LOGGING PART

def init_logging():
    log_dir = os.path.join(os.getcwd(), 'logs')  # Relative path to /logs
    log_file_path = os.path.join(log_dir, 'app.log')

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path),  # Log to file
            logging.StreamHandler()              # Optionally also log to the console
        ]
    )
    logging.info("logging initialized and logging file exists")



