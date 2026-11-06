import sqlite3

from meeting_analyzer.storage import MeetingStore


def test_meeting_round_trip_and_order(tmp_path):
    store = MeetingStore(tmp_path / "history.sqlite3")
    meeting = store.create("Встреча_Москва.webm")
    store.update(meeting["id"], status="ready", language="ru",
                 transcript="Привет, коллеги.", summary={"short_summary": "Обсудили план", "decisions": [], "next_tasks": [], "open_questions": []})
    result = store.get(meeting["id"])
    assert result["filename"] == "Встреча_Москва.webm"
    assert result["transcript"] == "Привет, коллеги."
    assert result["summary"]["short_summary"] == "Обсудили план"
    assert store.list()[0]["id"] == meeting["id"]


def test_cloud_source_and_duplicate_lookup_survive_store_reopen(tmp_path):
    path = tmp_path / "history.sqlite3"
    url = "https://drive.google.com/file/d/TEST_FILE_ID_1234567890ABCDE/view"
    store = MeetingStore(path)
    meeting = store.create("lesson.webm", source="cloud", source_url=url, phase="downloading")
    reopened = MeetingStore(path)
    found = reopened.find_by_source_url(url)
    assert found["id"] == meeting["id"]
    assert found["source"] == "cloud"
    assert found["phase"] == "downloading"


def test_existing_lite_database_is_migrated_without_losing_meetings(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE meetings (
            id TEXT PRIMARY KEY, filename TEXT NOT NULL, added_at TEXT NOT NULL,
            status TEXT NOT NULL, language TEXT, transcript TEXT, summary TEXT, error TEXT)""")
        db.execute("INSERT INTO meetings(id,filename,added_at,status) VALUES('old','older.webm','now','ready')")
    store = MeetingStore(path)
    record = store.get("old")
    assert record["filename"] == "older.webm"
    assert record["source"] == "manual"
    assert record["source_url"] is None
