from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from bachbot.config import get_settings
from bachbot.registry.manifests import DatasetManifest


class CorpusCatalog:
    def __init__(self, db_path: str | Path | None = None) -> None:
        settings = get_settings()
        self.db_path = Path(db_path or settings.cache_dir / "bachbot.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    manifest_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS records (
                    record_id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def register_manifest(self, manifest: DatasetManifest) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO datasets(dataset_id, manifest_json, updated_at)
                VALUES(?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(dataset_id)
                DO UPDATE SET manifest_json=excluded.manifest_json, updated_at=CURRENT_TIMESTAMP
                """,
                (manifest.dataset_id, json.dumps(manifest.model_dump(mode="json"))),
            )

    def list_datasets(self) -> list[DatasetManifest]:
        with self._connect() as connection:
            rows = connection.execute("SELECT manifest_json FROM datasets ORDER BY dataset_id").fetchall()
        return [DatasetManifest.model_validate(json.loads(row["manifest_json"])) for row in rows]

    def get_dataset(self, dataset_id: str) -> DatasetManifest | None:
        with self._connect() as connection:
            row = connection.execute("SELECT manifest_json FROM datasets WHERE dataset_id = ?", (dataset_id,)).fetchone()
        if row is None:
            return None
        return DatasetManifest.model_validate(json.loads(row["manifest_json"]))

    def upsert_record(self, record_id: str, record_type: str, payload: dict) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO records(record_id, record_type, payload_json, updated_at)
                VALUES(?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(record_id)
                DO UPDATE SET record_type=excluded.record_type, payload_json=excluded.payload_json, updated_at=CURRENT_TIMESTAMP
                """,
                (record_id, record_type, json.dumps(payload)),
            )

    def fetch_records(self, record_type: str | None = None) -> Iterable[dict]:
        query = "SELECT payload_json FROM records"
        params: tuple[str, ...] = ()
        if record_type:
            query += " WHERE record_type = ?"
            params = (record_type,)
        query += " ORDER BY record_id"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

