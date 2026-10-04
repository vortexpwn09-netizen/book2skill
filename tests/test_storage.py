from book2skill.storage import SQLiteStore


def test_sqlite_store_persists_projects_and_jobs(tmp_path):
    db = SQLiteStore(tmp_path / "book2skill.db")

    project_id = db.create_project("Alpha Project")
    db.add_document(project_id, "sample.md", "# Sample\n\nAI agents use context.")

    project = db.get_project(project_id)
    assert project["name"] == "Alpha Project"
    assert len(project["documents"]) == 1
    assert project["documents"][0]["filename"] == "sample.md"

    job_id = db.create_job("Deep Work", "AI agents use context and memory.")
    job = db.get_job(job_id)
    assert job["job_id"] == job_id
    assert job["status"] == "queued"
    assert job["title"] == "Deep Work"


def test_store_removes_legacy_pending_email_verifications(tmp_path):
    database_path = tmp_path / "legacy.db"
    db = SQLiteStore(database_path)
    with db._connect() as connection:
        connection.execute(
            "CREATE TABLE pending_email_verifications (email TEXT PRIMARY KEY, otp_hash TEXT NOT NULL)"
        )

    SQLiteStore(database_path)

    with db._connect() as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'pending_email_verifications'"
        ).fetchone()
    assert table is None
