"""Conexion a Postgres (Supabase o local). get_db_connection() es la entrada estandar."""
from __future__ import annotations

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("SUPABASE_DB_HOST"),
    "port":     os.getenv("SUPABASE_DB_PORT", "6543"),
    "dbname":   os.getenv("SUPABASE_DB_NAME", "postgres"),
    "user":     os.getenv("SUPABASE_DB_USER"),
    "password": os.getenv("SUPABASE_DB_PASSWORD"),
    "sslmode":  "require",
}


def get_db_connection() -> psycopg2.extensions.connection:
    """Crea una conexion fresca a Postgres."""
    return psycopg2.connect(**DB_CONFIG)
