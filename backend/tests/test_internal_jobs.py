def test_process_reminders_requires_the_shared_secret(client):
    response = client.post("/api/internal/jobs/process-reminders")
    assert response.status_code == 401


def test_process_reminders_rejects_a_wrong_secret(client):
    response = client.post(
        "/api/internal/jobs/process-reminders",
        headers={"X-Internal-Jobs-Secret": "not-the-real-secret"},
    )
    assert response.status_code == 401


def test_process_reminders_succeeds_with_the_right_secret(client, internal_jobs_header):
    response = client.post("/api/internal/jobs/process-reminders", headers=internal_jobs_header)
    assert response.status_code == 200
    assert response.json() == {"reminders_sent": 0}


def test_process_reminders_is_safe_to_call_repeatedly(client, internal_jobs_header):
    """Idempotency check for what pg_cron will do in production: calling the
    job twice in a row must never error or double-send (today there is
    nothing to send yet — see ReminderService — but the contract holds).
    """
    first = client.post("/api/internal/jobs/process-reminders", headers=internal_jobs_header)
    second = client.post("/api/internal/jobs/process-reminders", headers=internal_jobs_header)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == {"reminders_sent": 0}
