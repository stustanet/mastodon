import redis
from config import REDIS_HOST

r = redis.Redis(host='REDIS_HOST')


class Operation:

    def _init_(self, path, operation):
        self.path = path
        self.operation = operation
        self.operations = {
            "INIT"   : self.op_init,
            "CREATE" : self.op_create,
            "MOVE"   : self.op_move,
            "RENAME" : self.op_rename,
        }

    def operate(self):
        self.operations[self.operation]()


    # INOTIFY operation handlers
    def op_init(self):

    def op_create(self):

    def op_move(self):


def process_element(self):
    op = Operation(r.lpop("pending"))
    op.operate()


def process_queue(self):
    while True:
        process_element()


if __name__ == "__main__":
    process_queue()
