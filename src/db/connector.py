import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from psycopg import Connection


class DBConnector:
    def __init__(self) -> None:
        load_dotenv()

        self._host = os.environ["POSTGRES_HOST"]
        self._port = int(os.environ["POSTGRES_PORT"])
        self._database = os.environ["POSTGRES_DB"]
        self._user = os.environ["POSTGRES_USER"]
        self._password = os.environ["POSTGRES_PASSWORD"]

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        with psycopg.connect(
            host=self._host,
            port=self._port,
            dbname=self._database,
            user=self._user,
            password=self._password,
        ) as conn:
            yield conn
