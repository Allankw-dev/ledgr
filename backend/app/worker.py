"""Stand-alone queue worker:   python -m app.worker

Run as many as you like (locally, on other machines, as extra containers):
jobs are claimed with FOR UPDATE SKIP LOCKED so none is processed twice at once.
Set RUN_JOB_WORKER=false on the API instances when you do this.
"""

import logging
import signal
import threading

from app.core.jobs import worker_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

if __name__ == "__main__":
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    worker_loop(stop)
