import multiprocessing
import os
import shutil

from prometheus_client import multiprocess

bind = "0.0.0.0:8000"
workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count()))
worker_class = "uvicorn_worker.UvicornWorker"
preload_app = True
keepalive = 5
timeout = 30
graceful_timeout = 10
backlog = 2048
accesslog = None
errorlog = "-"


def on_starting(_server) -> None:
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if multiproc_dir:
        shutil.rmtree(multiproc_dir, ignore_errors=True)
        os.makedirs(multiproc_dir, exist_ok=True)


def child_exit(_server, worker) -> None:
    multiprocess.mark_process_dead(worker.pid)
