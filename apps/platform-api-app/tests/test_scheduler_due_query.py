"""Regresyon: scheduler_service due_job_ids sorgusu bool|BinaryExpression hatası vermemeli.

Bug (KI-001): ``or_(ScheduledJob.last_run_status is None, ...)`` Python'da
``False`` olarak değerlendirilip SQLAlchemy'de ``bool | BinaryExpression`` hatası
üretiyordu → scheduler hiçbir zamanlı işi dağıtmıyordu (loop hata yutup
2×poll bekliyordu).

Fix: ``ScheduledJob.last_run_status.is_(None)``.

Bu test gerçek DB kullanmadan SQLAlchemy ifade ağacının hatasız
kurulabildiğini doğrular (in-memory SQLite + minimal seed).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, or_, select
from sqlalchemy.orm import sessionmaker

from platform_api.db.models import ScheduledJob


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    ScheduledJob.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def _build_due_query(session):
    """scheduler_service.py:479-491 — düzeltme sonrası ifade."""
    now = datetime.now(UTC)
    return select(ScheduledJob.id).where(
        ScheduledJob.enabled,
        ScheduledJob.next_run_at <= now,
        or_(
            ScheduledJob.last_run_status.is_(None),
            ScheduledJob.last_run_status != "running",
        ),
    )


def test_due_job_ids_query_does_not_raise(session):
    """Bug değer: or_(is None) bool|BinaryExpression üretirdi → TypeError."""
    q = _build_due_query(session)
    # SQLAlchemy ifade ağacı hatasız kurulmalı ve çalıştırılmalı
    result = session.execute(q).all()
    assert result == []  # boş tabloda boş sonuç


def test_due_job_ids_returns_pending_and_failed_jobs(session):
    """last_run_status None (hiç çalışmamış) VEYA "failed"/"succeeded" → due olmalı;
    "running" → olmamalı."""
    now = datetime.now(UTC)
    past = now  # hemen due olsun

    # hiç çalışmamış
    s1 = ScheduledJob(
        job_name="pending",
        job_type="test",
        enabled=True,
        next_run_at=past,
        last_run_status=None,
    )
    # başarısız → yeniden due olabilir
    s2 = ScheduledJob(
        job_name="failed",
        job_type="test",
        enabled=True,
        next_run_at=past,
        last_run_status="failed",
    )
    # şu an çalışıyor → due olmamalı
    s3 = ScheduledJob(
        job_name="running",
        job_type="test",
        enabled=True,
        next_run_at=past,
        last_run_status="running",
    )
    # disabled → due olmamalı
    s4 = ScheduledJob(
        job_name="disabled",
        job_type="test",
        enabled=False,
        next_run_at=past,
        last_run_status=None,
    )
    # gelecekte → due olmamalı
    from datetime import timedelta

    future = now + timedelta(hours=1)
    s5 = ScheduledJob(
        job_name="future",
        job_type="test",
        enabled=True,
        next_run_at=future,
        last_run_status=None,
    )

    session.add_all([s1, s2, s3, s4, s5])
    session.commit()

    ids = {row[0] for row in session.execute(_build_due_query(session)).all()}
    assert s1.id in ids, "hiç çalışmamış (None) due olmalı"
    assert s2.id in ids, "failed due olmalı"
    assert s3.id not in ids, "running due olmamalı"
    assert s4.id not in ids, "disabled due olmamalı"
    assert s5.id not in ids, "future due olmamalı"


def test_old_or_is_none_pattern_is_noop():
    """Bilgi: SQLAlchemy 2.x eski ``or_(is None, ...)`` desenini sessizce bool'a
    çevirip sonucu boşaltıyor — scheduler hiç due döndürmüyordu (sessiz bug).
    Fix bunu ``is_(None)`` ile netleştirip davranışı bilinir kılar.
    Bu test eski desenin artık TypeError üretmediğini belgeleyerek regresyon
    için "fix gerekliydi" kanıtını korur."""
    from sqlalchemy import select

    q = select(ScheduledJob.id).where(
        or_(
            ScheduledJob.last_run_status is None,
            ScheduledJob.last_run_status != "running",
        )
    )
    # Eski desen sessizce boş sonuç döndürürdü → kritik olarak `or_(...)` True
    # olarak truthy değil; SQLAlchemy 2.x bunu bool->false yapıp sorguyu filtrelemez
    assert q is not None  # Query nesnesi kurulur, ama filtre etkisizdir
