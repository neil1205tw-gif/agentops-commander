import os

# app.main builds the module-level `app` on import, which needs DATABASE_URL.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/none")
os.environ.setdefault("APP_ENV", "test")
