"""In-process scheduler workers for lifecycle fixtures with local fake hosts."""

import multiprocessing
import threading

from silverquillm.karn.scheduler_worker import execute_worker


class ThreadWorker:
    def __init__(self, executor, arguments):
        self.connection, child = multiprocessing.Pipe()
        self.owner = None
        self.thread = threading.Thread(target=execute_worker, args=(child, executor, arguments))
        self.thread.start()

    def interrupt(self):
        pass

    def alive(self):
        return self.thread.is_alive()

    def close(self):
        self.thread.join()
        self.connection.close()
