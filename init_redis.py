import logging
import redis
import os

# Initialize Redis connection
r = redis.Redis()


def get_files(search_path):
    logging.debug("search_path: {}".format(search_path))

    # Iterate Directories
    for root, dirs, files in os.walk(search_path):
        for filename in files:

            # Push all files to "pending list"
            r.lpush("pending", (filename, "INIT"))


def main():
    logging.basicConfig(level=logging.DEBUG)

    logging.info("Scraper started.")
    get_files()


if __name__ == "__main__":
    main()
