from datetime import datetime, timedelta, timezone

from app.models.compliance_request import ComplianceRequest
from tests.conftest import TestingSessionLocal

USER_A = "11111111-1111-1111-1111-111111111111"


def _onboard(client, headers, name="Acme BV", country="NL"):
    return client.post("/api/companies", json={"name": name, "country": country}, headers=headers)


def _create_supplier(client, headers, name="Shenzhen Wonderful Packaging", email="s@example.com"):
    return client.post(
        "/api/suppliers", json={"name": name, "email": email}, headers=headers
    ).json()


def _create_product(client, headers, supplier_id, name="Bamboo toothbrush"):
    return client.post(
        "/api/products", json={"name": name, "supplier_id": supplier_id}, headers=headers
    ).json()


def _send_request(client, headers, supplier, product):
    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "es"},
        headers=headers,
    ).json()
    client.post(f"/api/requests/{request['id']}/send", headers=headers)
    return request


def _age_sent_at(request_id: str, days: int):
    with TestingSessionLocal() as db:
        record = db.get(ComplianceRequest, request_id)
        record.sent_at = datetime.now(timezone.utc) - timedelta(days=days)
        db.commit()


def test_reminder_not_due_before_schedule(client, auth_header, internal_jobs_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _send_request(client, headers, supplier, product)

    response = client.post("/api/internal/jobs/process-reminders", headers=internal_jobs_header)
    assert response.json() == {"reminders_sent": 0}


def test_reminder_sent_once_schedule_elapses(client, auth_header, internal_jobs_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    request = _send_request(client, headers, supplier, product)
    _age_sent_at(request["id"], days=4)  # schedule default: [3, 7, 14]

    response = client.post("/api/internal/jobs/process-reminders", headers=internal_jobs_header)
    assert response.json() == {"reminders_sent": 1}

    updated = client.get(f"/api/requests/{request['id']}", headers=headers).json()
    assert updated is not None  # sanity: request still readable/company-scoped


def test_reminder_not_sent_twice_for_the_same_interval(client, auth_header, internal_jobs_header):
    """Idempotency: calling the job twice in a row (simulating overlapping
    cron invocations) must never send the same interval's reminder twice."""
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    request = _send_request(client, headers, supplier, product)
    _age_sent_at(request["id"], days=4)

    first = client.post("/api/internal/jobs/process-reminders", headers=internal_jobs_header)
    second = client.post("/api/internal/jobs/process-reminders", headers=internal_jobs_header)
    assert first.json() == {"reminders_sent": 1}
    assert second.json() == {"reminders_sent": 0}


def test_reminder_uses_follow_up_template_once_a_round_exists(
    client, auth_header, internal_jobs_header, recording_email_sender
):
    """A reminder re-delivers whatever's currently live — the initial
    template before any round exists, the missing-information template
    once one does — without creating a new FollowUpRound itself (see
    ReminderService/FollowUpService.send_reminder docstrings)."""
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    client.post(
        f"/api/products/{product['id']}/packaging-components",
        json={"name": "Outer box", "packaging_type": "box"},
        headers=headers,
    )
    request = _send_request(client, headers, supplier, product)
    client.post(f"/api/requests/{request['id']}/follow-up", headers=headers)

    before_rounds = client.get(f"/api/requests/{request['id']}", headers=headers).json()[
        "follow_up_rounds"
    ]
    _age_sent_at(request["id"], days=100)  # doesn't matter — anchor is now the round's created_at
    with TestingSessionLocal() as db:
        record = db.get(ComplianceRequest, request["id"])
        record.reminder_count = 0
        db.commit()

    # Force the round's created_at far enough in the past to be due.
    from app.models.follow_up_round import FollowUpRound

    with TestingSessionLocal() as db:
        round_ = db.query(FollowUpRound).filter_by(request_id=request["id"]).first()
        round_.created_at = datetime.now(timezone.utc) - timedelta(days=4)
        db.commit()

    client.post("/api/internal/jobs/process-reminders", headers=internal_jobs_header)

    after_rounds = client.get(f"/api/requests/{request['id']}", headers=headers).json()[
        "follow_up_rounds"
    ]
    assert len(after_rounds) == len(before_rounds)  # no new round created by the reminder

    sent = recording_email_sender.sent_messages
    assert "still need" in sent[-1].html_body or "todavía necesitamos" in sent[-1].html_body.lower()
