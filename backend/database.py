import hashlib
import time
import logging

from backend.config import Config

security_logger = logging.getLogger("security")

import pymysql


def get_connection(retries=3, delay=1):
    for attempt in range(retries):
        try:
            return pymysql.connect(
                host=Config.DATABASE_HOST,
                port=Config.DATABASE_PORT,
                user=Config.DATABASE_USER,
                password=Config.DATABASE_PASSWORD,
                database=Config.DATABASE_NAME,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                connect_timeout=5,
                read_timeout=10,
            )
        except pymysql.Error as e:
            security_logger.warning(f"DB connection attempt {attempt + 1}/{retries} failed: {e}")
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def execute_query(sql, params=None, fetch=True):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            if fetch:
                return cursor.fetchall()
            return cursor.lastrowid
    finally:
        conn.close()


def execute_insert(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            conn.commit()
            return cursor.lastrowid
    finally:
        conn.close()


def execute_update(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount
    finally:
        conn.close()


_token_blacklist = set()


def blacklist_token(token):
    _token_blacklist.add(token)


def is_token_blacklisted(token):
    return token in _token_blacklist


def init_default_admin():
    from backend.utils.security import hash_password

    admins = execute_query("SELECT id FROM admins LIMIT 1")
    if not admins:
        pw = hash_password("admin")
        execute_insert(
            "INSERT INTO admins (username, password_hash, role, status) VALUES (%s, %s, 'admin', 'active')",
            ("admin", pw),
        )
        security_logger.info("Default admin user created (admin/admin)")
        print("[DB] Default admin user created (admin/admin)")


def cleanup_blacklist():
    import threading

    def _cleanup():
        while True:
            time.sleep(3600)
            if len(_token_blacklist) > 10000:
                _token_blacklist.clear()
                security_logger.info("Token blacklist cleared (too large)")

    t = threading.Thread(target=_cleanup, daemon=True)
    t.start()
