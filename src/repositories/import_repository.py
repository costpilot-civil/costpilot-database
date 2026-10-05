from psycopg import Connection


class ImportRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def upsert_data_source(
        self,
        *,
        code: str,
        name: str,
        source_type: str,
        description: str | None,
    ) -> int:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO data_sources (
                    code,
                    name,
                    source_type,
                    description
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (code)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    source_type = EXCLUDED.source_type,
                    description = EXCLUDED.description
                RETURNING id;
                """,
                (
                    code,
                    name,
                    source_type,
                    description,
                ),
            )

            row = cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to upsert data source.")

        return int(row[0])

    def create_import_log(
        self,
        *,
        data_source_id: int,
        file_name: str | None,
        file_hash: str | None,
    ) -> int:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO import_logs (
                    data_source_id,
                    file_name,
                    file_hash,
                    status,
                    started_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'RUNNING',
                    NOW()
                )
                RETURNING id;
                """,
                (
                    data_source_id,
                    file_name,
                    file_hash,
                ),
            )

            row = cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to create import log.")

        return int(row[0])

    def mark_import_succeeded(
        self,
        *,
        import_log_id: int,
        records_total: int,
        records_imported: int,
    ) -> None:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE import_logs
                SET
                    status = 'SUCCEEDED',
                    records_total = %s,
                    records_imported = %s,
                    error_message = NULL,
                    finished_at = NOW()
                WHERE id = %s;
                """,
                (
                    records_total,
                    records_imported,
                    import_log_id,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(f"Import log {import_log_id} was not found.")

    def mark_import_failed(
        self,
        *,
        import_log_id: int,
        error_message: str,
    ) -> None:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE import_logs
                SET
                    status = 'FAILED',
                    error_message = %s,
                    finished_at = NOW()
                WHERE id = %s;
                """,
                (
                    error_message,
                    import_log_id,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(f"Import log {import_log_id} was not found.")
