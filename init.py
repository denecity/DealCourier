import logging
import os
import utils.init
import subprocess
import sys



def ensure_package_installed(package_name):
    """
    Checks if a package is installed, and installs it if not.
    """
    try:
        __import__(package_name)
        print("yaml is already installed")
    except ImportError:
        print(f"Package '{package_name}' not found, installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

# 1. Ensure 'yaml' (PyYAML) is installed
ensure_package_installed("yaml")

from utils.utils import init_logging
from utils.utils import load_config
import scrape

#######################
# INITIALIZE LOGGING
#######################


init_logging()
logging.info("")
logging.info("START OF INSTANCE ################")

config = load_config()

def main():
    logging.info("Starting application...")
    
    utils.init.run_initialization(config)


if __name__ == "__main__":
    main()
