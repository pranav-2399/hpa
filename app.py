# This file is kept for backward compatibility.
# The app now lives in the `app/` package.
# Use `run.py` as the entry point:
#
#   python run.py
#   gunicorn -w 4 -b 0.0.0.0:5000 run:app
#
from run import app  # noqa: F401

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
