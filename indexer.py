import redis
from config import REDIS_HOST
import logging
import pickle

r = redis.Redis(host=REDIS_HOST)


class Operation:

    def __init__(self, path, operation):
        self.path = path
        self.operation = operation
        self.operations = {
            "INIT"   : self.op_init,
            "CREATE" : self.op_create,
            "MOVE"   : self.op_move,
            "RENAME" : self.op_rename,
        }

    def operate(self):
        logging.debug("operation init: {}".format(self.path))
        self.operations[self.operation]()

    # INOTIFY operation handlers
    def op_init(self):
        pass

    def op_create(self):
        pass

    def op_move(self):
        pass


def process_element():
    el = r.rpop("pending")
    op = Operation(pickle.loads(el))
    op.operate()


def process_queue():
    while True:
        process_element()


if __name__ == "__main__":
    process_queue()
