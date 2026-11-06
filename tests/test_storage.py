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
