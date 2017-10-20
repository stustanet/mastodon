import logging
from config import PATH_TO_MOUNT, INDEX_FOLDER
import redis
import os
import pickle

# Initialize Redis connection
r = redis.Redis()


def add_files(search_path):
    logging.debug("search_path: {}".format(search_path))

    # Iterate Directories
    for root, dirs, files in os.walk(search_path):
        for filename in files:

            bytestr = pickle.dumps((filename, "INIT"))
            print(bytestr)
            # Push all files to "pending list"
            r.lpush("pending", bytestr)


def main():
    logging.basicConfig(level=logging.DEBUG)

    logging.info("Scraper started.")

    # Add files in INDEX_FOLDERs to redis list
    for folder in INDEX_FOLDER:
        add_files(os.path.join(PATH_TO_MOUNT, folder))

if __name__ == "__main__":
    main()
