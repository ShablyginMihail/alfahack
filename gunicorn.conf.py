import multiprocessing
import os

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
