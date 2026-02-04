import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_class = os.environ.get(
    "GUNICORN_WORKER_CLASS",
    "gthread",
)
worker_connections = 1000
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"


def post_fork(server, worker):
    from wsgi import app

    if hasattr(app, "start_services"):
        app.start_services()


def worker_exit(server, worker):
    from wsgi import app

    if hasattr(app, "stop_services"):
        app.stop_services()
