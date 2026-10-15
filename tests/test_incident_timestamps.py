import sys
import os
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.models.all import Incident, IncidentStatus, Severity, IncidentEvent
from app.schemas.all import IncidentResponse, IncidentEventResponse, IncidentCreate, serialize_utc_datetime
from app.api.incidents import create_incident, get_incidents


def test_serialize_utc_datetime_helper():
    # Naive UTC datetime gets 'Z'
    naive_dt = datetime(2026, 10, 4, 10, 13, 40, 407483)
    assert serialize_utc_datetime(naive_dt) == "2026-10-04T10:13:40.407483Z"

    # Timezone-aware UTC datetime gets 'Z'
    aware_dt = datetime(2026, 10, 4, 10, 13, 40, tzinfo=timezone.utc)
    assert serialize_utc_datetime(aware_dt) == "2026-10-04T10:13:40Z"

    # Non-UTC timezone is converted to UTC
    plus_530 = timezone(timedelta(hours=5, minutes=30))
    local_dt = datetime(2026, 10, 4, 15, 43, 40, tzinfo=plus_530)
    assert serialize_utc_datetime(local_dt) == "2026-10-04T10:13:40Z"

    # None returns None
    assert serialize_utc_datetime(None) is None


def test_incident_response_timestamp_serialization():
    class MockIncident:
        id = 1
        incident_id = "INC-TEST-001"
        title = "Database Connection Timeout"
        description = "High pool usage"
        status = IncidentStatus.DETECTED
        severity = Severity.HIGH
        affected_service = "payment-service"
        fault_type = "http_500_spike"
        created_at = datetime(2026, 10, 4, 10, 13, 40, 407483)
        updated_at = datetime(2026, 10, 4, 10, 15, 0)
        started_at = None
        resolved_at = datetime(2026, 10, 4, 10, 30, 0)

    resp = IncidentResponse.model_validate(MockIncident())
    dumped = resp.model_dump(mode="json")

    assert dumped["created_at"] == "2026-10-04T10:13:40.407483Z"
    assert dumped["updated_at"] == "2026-10-04T10:15:00Z"
    assert dumped["started_at"] is None
    assert dumped["resolved_at"] == "2026-10-04T10:30:00Z"
    assert resp.created_at == datetime(2026, 10, 4, 10, 13, 40, 407483)


def test_incident_event_response_serialization():
    class MockEvent:
        event_type = "INCIDENT_CREATED"
        source = "incident-api"
        message = "Incident created"
        timestamp = datetime(2026, 10, 12, 18, 0, 0)
        metadata_json = {}

    resp = IncidentEventResponse.model_validate(MockEvent())
    dumped = resp.model_dump(mode="json")
    assert dumped["timestamp"] == "2026-10-12T18:00:00Z"


def test_create_incident_generates_current_timestamp():
    db = MagicMock()
    created_entities = []

    def mock_add(entity):
        created_entities.append(entity)

    db.add.side_effect = mock_add

    payload = IncidentCreate(
        title="Live Demo Incident",
        description="Triggered during presentation",
        severity=Severity.HIGH,
        affected_service="payment-service",
        fault_type="http_500_spike"
    )

    before = datetime.utcnow()
    res = create_incident(payload, db=db)
    after = datetime.utcnow()

    # Verify incident was created with current timestamp
    assert res.created_at is not None
    assert before <= res.created_at <= after
    assert before <= res.updated_at <= after

    # Verify INCIDENT_CREATED event timestamp matches
    event = [e for e in created_entities if isinstance(e, IncidentEvent)][0]
    assert before <= event.timestamp <= after


def test_get_incidents_orders_newest_first():
    db = MagicMock()
    query_mock = MagicMock()
    order_mock = MagicMock()

    db.query.return_value = query_mock
    query_mock.order_by.return_value = order_mock

    # Setup 3 mock incidents with different historical dates
    inc_old = Incident(id=1, incident_id="INC-OLD", created_at=datetime(2026, 10, 4, 10, 0, 0))
    inc_mid = Incident(id=2, incident_id="INC-MID", created_at=datetime(2026, 10, 8, 12, 0, 0))
    inc_new = Incident(id=3, incident_id="INC-NEW", created_at=datetime(2026, 10, 13, 1, 0, 0))

    # The DB ordering should return newest first
    order_mock.all.return_value = [inc_new, inc_mid, inc_old]

    results = get_incidents(db=db)

    # Verify order_by was called with descending created_at
    query_mock.order_by.assert_called_once()
    assert results[0].incident_id == "INC-NEW"
    assert results[1].incident_id == "INC-MID"
    assert results[2].incident_id == "INC-OLD"


def test_historical_timestamps_preserved():
    # Verify that existing incidents retain their historical timestamp
    historical_date = datetime(2026, 10, 4, 10, 13, 40, 407483)
    inc = Incident(
        id=1,
        incident_id="INC-HISTORICAL",
        title="Historical Incident",
        status=IncidentStatus.RESOLVED,
        severity=Severity.HIGH,
        created_at=historical_date,
        updated_at=historical_date,
        resolved_at=datetime(2026, 10, 4, 10, 45, 0)
    )

    resp = IncidentResponse.model_validate(inc)
    dumped = resp.model_dump(mode="json")

    # Timestamps are strictly preserved, not rewritten to now
    assert dumped["created_at"] == "2026-10-04T10:13:40.407483Z"
    assert dumped["resolved_at"] == "2026-10-04T10:45:00Z"


def test_get_incidents_order_by_nullslast_and_id_desc():
    db = MagicMock()
    query_mock = MagicMock()
    order_mock = MagicMock()

    db.query.return_value = query_mock
    query_mock.order_by.return_value = order_mock
    order_mock.all.return_value = []

    get_incidents(db=db)

    # Verify query.order_by received created_at.desc().nullslast() and id.desc()
    query_mock.order_by.assert_called_once()
    args = query_mock.order_by.call_args[0]
    assert len(args) == 2
    # First arg is created_at descending with nulls last
    assert "created_at" in str(args[0])
    assert "DESC" in str(args[0])
    # Second arg is id descending
    assert "id" in str(args[1])
    assert "DESC" in str(args[1])


def test_sqlalchemy_query_execution_equal_and_null_timestamps():
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import sessionmaker
    from app.models.all import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    t_same = datetime(2026, 10, 10, 12, 0, 0)
    t_newer = datetime(2026, 10, 15, 12, 0, 0)

    # Insert items with:
    # id=1: old same time
    # id=2: newer same time
    # id=3: newest time
    # id=4: NULL created_at (updated explicitly to bypass client-side default)
    session.add(Incident(id=1, incident_id="INC-SAME-1", title="T1", severity=Severity.LOW, created_at=t_same))
    session.add(Incident(id=2, incident_id="INC-SAME-2", title="T2", severity=Severity.LOW, created_at=t_same))
    session.add(Incident(id=3, incident_id="INC-NEWEST", title="T3", severity=Severity.LOW, created_at=t_newer))
    session.add(Incident(id=4, incident_id="INC-NULL", title="T4", severity=Severity.LOW, created_at=t_same))
    session.commit()

    # Explicitly set created_at to NULL on id=4 in the DB
    session.execute(update(Incident).where(Incident.id == 4).values(created_at=None))
    session.commit()

    results = get_incidents(db=session)

    # 1. Newest timestamp first
    assert results[0].incident_id == "INC-NEWEST"
    # 2. Equal timestamps tie-broken by id DESC (id 2 before id 1)
    assert results[1].incident_id == "INC-SAME-2"
    assert results[2].incident_id == "INC-SAME-1"
    # 3. NULL timestamp ordered last via .nullslast()
    assert results[3].incident_id == "INC-NULL"

    session.close()
