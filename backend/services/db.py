# backend/services/db.py
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
_engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None


def init_schema() -> None:
    """Create core tables if a database connection is available."""
    if not _engine:
        return
    table_ddl = """
    CREATE TABLE IF NOT EXISTS uploaded_files (
      id BIGSERIAL PRIMARY KEY,
      file_id TEXT NOT NULL,
      file_name TEXT NOT NULL,
      content_type TEXT,
      category TEXT NOT NULL,
      size_bytes BIGINT NOT NULL,
      sha256 TEXT,
      content BYTEA NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS json_configs (
      id BIGSERIAL PRIMARY KEY,
      file_id TEXT NOT NULL,
      name TEXT NOT NULL,
      content JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS generated_reports (
      id BIGSERIAL PRIMARY KEY,
      file_id TEXT NOT NULL,
      report_name TEXT NOT NULL,
      content_type TEXT NOT NULL,
      size_bytes BIGINT NOT NULL,
      sha256 TEXT,
      content BYTEA NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """
    index_ddl = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_uploaded_files_file_id ON uploaded_files (file_id);
    CREATE INDEX IF NOT EXISTS idx_json_configs_file_id ON json_configs (file_id, name);
    CREATE INDEX IF NOT EXISTS idx_generated_reports_file_id ON generated_reports (file_id);
    """
    with _engine.begin() as conn:
        for stmt in table_ddl.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
        for stmt in index_ddl.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))


def save_raw_file(
    file_id: str,
    file_name: str,
    content: bytes,
    category: str,
    content_type: Optional[str],
) -> None:
    if not _engine:
        return
    sha256 = hashlib.sha256(content).hexdigest()
    with _engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO uploaded_files (file_id, file_name, content_type, category, size_bytes, sha256, content)
                VALUES (:file_id, :file_name, :content_type, :category, :size_bytes, :sha256, :content)
                ON CONFLICT (file_id) DO UPDATE
                SET file_name = EXCLUDED.file_name,
                    content_type = EXCLUDED.content_type,
                    category = EXCLUDED.category,
                    size_bytes = EXCLUDED.size_bytes,
                    sha256 = EXCLUDED.sha256,
                    content = EXCLUDED.content,
                    created_at = now()
                """
            ),
            dict(
                file_id=file_id,
                file_name=file_name,
                content_type=content_type,
                category=category,
                size_bytes=len(content),
                sha256=sha256,
                content=content,
            ),
        )


def save_json_config(file_id: str, name: str, content_obj: dict) -> None:
    if not _engine:
        return
    with _engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO json_configs (file_id, name, content)
                VALUES (:file_id, :name, CAST(:content AS jsonb))
                """
            ),
            dict(file_id=file_id, name=name, content=json.dumps(content_obj, ensure_ascii=False)),
        )


def save_report_file(file_id: str, report_name: str, content: bytes) -> Optional[int]:
    if not _engine:
        return None
    sha256 = hashlib.sha256(content).hexdigest()
    with _engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO generated_reports (file_id, report_name, content_type, size_bytes, sha256, content)
                VALUES (:file_id, :report_name, :content_type, :size_bytes, :sha256, :content)
                RETURNING id
                """
            ),
            dict(
                file_id=file_id,
                report_name=report_name,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                size_bytes=len(content),
                sha256=sha256,
                content=content,
            ),
        ).first()
        return row[0] if row else None


def get_report_file(report_id: int) -> Optional[Tuple[str, str, bytes]]:
    if not _engine:
        return None
    with _engine.begin() as conn:
        row = conn.execute(
            text("SELECT report_name, content_type, content FROM generated_reports WHERE id = :id"),
            dict(id=report_id),
        ).first()
        return row if row else None


def get_report_file_by_name(report_name: str) -> Optional[Tuple[str, str, bytes]]:
    if not _engine:
        return None
    with _engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT report_name, content_type, content "
                "FROM generated_reports WHERE report_name = :report_name"
            ),
            dict(report_name=report_name),
        ).first()
        return row if row else None


def get_uploaded_file(file_id: str) -> Optional[Tuple[str, Optional[str], str, bytes]]:
    """
    Returns (file_name, content_type, category, content) for the given file_id.
    """
    if not _engine:
        return None
    with _engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT file_name, content_type, category, content "
                "FROM uploaded_files WHERE file_id = :file_id"
            ),
            dict(file_id=file_id),
        ).first()
        return row if row else None


@contextmanager
def materialize_uploaded_file(file_id: str) -> Iterator[Tuple[Path, Dict[str, Any]]]:
    """
    Context manager that writes the uploaded file content to a temporary file and yields its path
    along with basic metadata. The temporary file will be removed automatically.
    """
    record = get_uploaded_file(file_id)
    if not record:
        raise FileNotFoundError(f"No uploaded file found for id {file_id}")

    file_name, content_type, category, content = record
    suffix = Path(file_name).suffix or ".tmp"
    temp_dir = Path(tempfile.mkdtemp(prefix="driadb_"))
    temp_path = temp_dir / f"{file_id}{suffix}"
    temp_path.write_bytes(content)
    metadata = {
        "file_name": file_name,
        "content_type": content_type,
        "category": category,
        "size_bytes": len(content),
    }

    try:
        yield temp_path, metadata
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            temp_dir.rmdir()
        except OSError:
            pass


def list_uploaded_files() -> List[Dict[str, Any]]:
    if not _engine:
        return []
    with _engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT file_id, file_name, content_type, category, size_bytes, sha256, created_at "
                "FROM uploaded_files ORDER BY created_at DESC"
            )
        ).fetchall()
        return [
            dict(
                file_id=row.file_id,
                file_name=row.file_name,
                content_type=row.content_type,
                category=row.category,
                size=row.size_bytes,
                sha256=row.sha256,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
            for row in rows
        ]


def delete_uploaded_file(file_id: str) -> bool:
    if not _engine:
        return False
    with _engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM uploaded_files WHERE file_id = :file_id"),
            dict(file_id=file_id),
        )
    return result.rowcount > 0