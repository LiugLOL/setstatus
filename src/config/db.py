"""PostgreSQL connection setup for the SetStatus application."""

import os
from contextlib import contextmanager
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in environment variables")


@contextmanager
def get_connection():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn