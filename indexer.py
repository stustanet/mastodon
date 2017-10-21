import redis
from config import REDIS_HOST
import logging
import pickle
import hashlib
from api.models import Media

r = redis.Redis(host=REDIS_HOST)


class Operation:

    def __init__(self, path, operation):
        self.path = path
        self.operation = operation
        self.operations = {
            "INIT": self.op_init,
            "CREATE": self.op_create,
            "MOVE": self.op_move,
            "RENAME": self.op_rename,
        }

    def operate(self):
        logging.debug("operation: {} {}".format(self.path, self.operation))
        self.operations[self.operation]()

    # INOTIFY operation handlers
    def op_init(self):
        logging.debug("Initial Hash: {}".format(self.path))
        self.op_create()

    def op_create(self):
        with open(self.path, 'r') as f:
            # Hash the file
            hash_str = hashlib.sha256(f.read().encode())
            # Create new file object and add to db
            db_file = create_new_file(hash_str, self.path)
            File.add(db_file)
            #  Lookup if hash already exists
            query = Media.query().filter_by(file_hash=hash_str)
            if query is None:
                pass
            else:
                pass

    def op_rename(self):
        pass

    def op_truncate(self):
        pass

    def op_mkdir(self):
        pass

    def op_deldir(self):
        pass


def create_new_file():
    pass


def process_element():
    res = r.rpop("pending")
    if res is not None:
        obj = pickle.loads(res)
        op = Operation(*obj)
        op.operate()


def process_queue():
    while True:
        process_element()


if __name__ is "__main__":
    logging.basicConfig(level=logging.DEBUG)
    process_queue()
