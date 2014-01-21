"""
Created on Jan 21, 2014

@author: Kazantsev Alexey <a.kazantsev@samsung.com>,
         Vadim Markovtsev <v.markovtsev@samsung.com>
"""


import copy
import logging
from queue import Queue
import signal
import sys
import types
from twisted.python import threadpool


class ThreadPool(threadpool.ThreadPool):
    """
    Pool of threads.
    """

    sysexit_initial = None
    sigint_initial = None
    pools = []

    def __init__(self, minthreads=5, maxthreads=20, name=None):
        """
        Creates a new thread pool and starts it.
        """
        super(ThreadPool, self).__init__()
        self.start()
        self.on_shutdowns = []
        if not ThreadPool.pools:
            ThreadPool.sysexit_initial = sys.exit
            sys.exit = ThreadPool.exit
            ThreadPool.sigint_initial = \
                signal.signal(signal.SIGINT, ThreadPool.sigint_handler)
        ThreadPool.pools.append(self)

    def __fini__(self):
        if not self.joined:
            self.shutdown(False, True)

    def request(self, run, args=()):
        """
        Tuple version of callInThread().
        """
        self.callInThread(run, *args)

    def register_on_shutdown(self, func):
        """
        Adds the specified function to the list of callbacks which are
        executed before shutting down the thread pool.
        It is useful when an infinite event loop is executed in a separate
        thread and a graceful shutdown is desired. Then on_shutdown() function
        shall terminate that loop using the corresponding foreign API.
        """
        self.on_shutdowns.append(func)

    def _put(self, item):
        """
        Private method used by shutdown() to redefine Queue's _put().
        """
        self.queue.appendleft(item)

    def shutdown(self, execute_remaining=False, force=False, timeout=0.25):
        """Safely brings thread pool down.
        """
        for on_shutdown in self.on_shutdowns:
            on_shutdown()
        self.on_shutdowns.clear()
        self.joined = True
        threads = copy.copy(self.threads)
        if not execute_remaining:
            self.q._put = types.MethodType(ThreadPool._put, self.q)
        while self.workers:
            self.q.put(threadpool.WorkerStop)
            self.workers -= 1
        for thread in threads:
            if not force:
                thread.join()
            else:
                thread.join(timeout)
                if thread.is_alive():
                    thread._stop()
                    logging.warning("Failed to join with thread #%d " +
                                    "since the timeout (%.2f sec) was " +
                                    "exceeded. It was killed.",
                                    thread.ident, timeout)
        ThreadPool.pools.remove(self)

    @staticmethod
    def shutdown_pools():
        """
        Private method to shut down all the pools.
        """
        pools = copy.copy(ThreadPool.pools)
        for pool in pools:
            pool.shutdown()

    @staticmethod
    def exit(retcode=0):
        """
        Terminates the running program safely.
        """
        ThreadPool.shutdown_pools()
        sys.exit = ThreadPool.sysexit_initial
        sys.exit(retcode)

    @staticmethod
    def sigint_handler(signal, frame):
        """
        Private method - handler for SIGINT.
        """
        ThreadPool.shutdown_pools()
        ThreadPool.sigint_initial(signal, frame)
