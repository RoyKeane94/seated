web: gunicorn config.wsgi --bind 0.0.0.0:$PORT --log-file -
worker: celery -A config worker --loglevel=info
beat: celery -A config beat --loglevel=info
