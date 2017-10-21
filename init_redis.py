#!bin/python3
import logging
from config import PATH_TO_MOUNT, INDEX_FOLDER, REDIS_HOST
import redis
import os
import pickle

# Initialize Redis connection
r = redis.Redis(host=REDIS_HOST)


def add_files(search_path):
    print("search_path: {}".format(search_path))

    # Iterate Directories
    for root, dirs, files in os.walk(search_path):
        for filename in files:
            logging.debug("Adding to queue: {}".format(filename))
            bytestr = pickle.dumps((filename, "INIT"))
            # Push all files to "pending list"
            r.lpush("pending", bytestr)


def main():
    logging.basicConfig(level=logging.DEBUG)

    logging.info("Scraper started.")

    # Add files in INDEX_FOLDERs to redis list
    for folder in INDEX_FOLDER:
        add_files(os.path.join(PATH_TO_MOUNT, folder))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
