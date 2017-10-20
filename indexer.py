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
        logging.debug("operation: {} {}".format(self.path, self.operation))
        self.operations[self.operation]()

    # INOTIFY operation handlers
    def op_init(self):
        pass

    def op_create(self):
        pass

    def op_move(self):
        pass

    def op_rename(self):
        pass


def process_element():
    res = r.rpop("pending")
    if res is None:
        obj = pickle.loads(res)
        op = Operation(*obj)
        op.operate()



def process_queue():
    while True:
        process_element()


if __name__ == "__main__":
    logging.basicConfig()
    process_queue()
