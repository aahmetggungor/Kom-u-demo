from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def uid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    display_name: Mapped[str] = mapped_column(String(160))


class Membership(Base):
    __tablename__ = "memberships"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(24))
    __table_args__ = (CheckConstraint("role IN ('admin','coordinator','rescue-team','observer')"),)


class AccessToken(Base):
    __tablename__ = "access_tokens"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str] = mapped_column(String(36))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["memberships.tenant_id", "memberships.user_id"]
        ),
    )


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="OPEN")
    verification_status: Mapped[str] = mapped_column(String(24), default="UNVERIFIED")
    urgency_level: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    incident_type: Mapped[str] = mapped_column(String(24), default="unknown")
    needs: Mapped[list] = mapped_column(JSON, default=list)
    ai_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    location_status: Mapped[str] = mapped_column(String(32), default="AMBIGUOUS_LOCATION")
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    region: Mapped[str | None] = mapped_column(String(160))
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    assigned_team_id: Mapped[str | None] = mapped_column(String(36))
    merged_into_id: Mapped[str | None] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "assigned_team_id"], ["teams.tenant_id", "teams.id"]),
        ForeignKeyConstraint(
            ["tenant_id", "merged_into_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_merge_target",
        ),
        CheckConstraint(
            "status IN ('OPEN','DISPATCHED','RESOLVED','MERGED')", name="ck_cases_status"
        ),
        CheckConstraint(
            "(status = 'MERGED' AND merged_into_id IS NOT NULL AND merged_into_id <> id) OR (status <> 'MERGED' AND merged_into_id IS NULL)",
            name="ck_cases_merge_state",
        ),
        CheckConstraint("verification_status IN ('UNVERIFIED','VERIFIED','REJECTED')"),
        CheckConstraint(
            "(lat IS NULL AND lon IS NULL) OR (lat BETWEEN -90 AND 90 AND lon BETWEEN -180 AND 180)"
        ),
    )


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    client_id: Mapped[str] = mapped_column(String(36))
    case_id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(24))
    original_text: Mapped[str] = mapped_column(Text)
    original_language: Mapped[str] = mapped_column(String(8), default="und")
    address_raw: Mapped[str | None] = mapped_column(String(1000))
    reported_lat: Mapped[float | None] = mapped_column(Float)
    reported_lon: Mapped[float | None] = mapped_column(Float)
    payload_hash: Mapped[str] = mapped_column(String(64))
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    processing_status: Mapped[str] = mapped_column(String(24), default="QUEUED")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id"),
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "case_id"], ["cases.tenant_id", "cases.id"]),
        Index("ix_reports_case", "tenant_id", "case_id"),
    )


class AudioAsset(Base):
    __tablename__ = "audio_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    report_id: Mapped[str] = mapped_column(String(36))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(24), default="QUARANTINED")
    content_type: Mapped[str] = mapped_column(String(40), default="audio/wav")
    plaintext_bytes: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    encryption_key_id: Mapped[str] = mapped_column(String(80))
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    content_hmac: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    scanner_revision: Mapped[str | None] = mapped_column(String(160))
    scan_verdict: Mapped[str | None] = mapped_column(String(24))
    scan_reason_code: Mapped[str | None] = mapped_column(String(80))
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    decision_reason: Mapped[str | None] = mapped_column(String(500))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "report_id"], ["reports.tenant_id", "reports.id"]),
        UniqueConstraint("tenant_id", "report_id"),
        CheckConstraint(
            "state IN ('QUARANTINED','SCAN_PASSED','SCAN_ERROR','RELEASED','REJECTED')",
            name="ck_audio_assets_state",
        ),
        CheckConstraint("version >= 1", name="ck_audio_assets_version"),
        CheckConstraint(
            "scan_verdict IS NULL OR scan_verdict IN ('CLEAN','MALICIOUS','INVALID','ERROR')",
            name="ck_audio_assets_scan_verdict",
        ),
        CheckConstraint("plaintext_bytes BETWEEN 1 AND 2000000"),
        CheckConstraint("duration_ms BETWEEN 200 AND 30000"),
    )


class AudioTranscript(Base):
    __tablename__ = "audio_transcripts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    audio_asset_id: Mapped[str] = mapped_column(ForeignKey("audio_assets.id", ondelete="CASCADE"))
    report_id: Mapped[str] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(24), default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_id: Mapped[str | None] = mapped_column(String(36))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    original_text: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(8))
    model_revision: Mapped[str | None] = mapped_column(String(200))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    source_audio_hmac: Mapped[str | None] = mapped_column(String(64))
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    error_code: Mapped[str | None] = mapped_column(String(80))
    corrected_text: Mapped[str | None] = mapped_column(Text)
    corrected_language: Mapped[str | None] = mapped_column(String(8))
    corrected_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    correction_reason: Mapped[str | None] = mapped_column(String(500))
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "report_id"], ["reports.tenant_id", "reports.id"]),
        UniqueConstraint("tenant_id", "audio_asset_id"),
        CheckConstraint("state IN ('QUEUED','RUNNING','DONE','FAILED')"),
        CheckConstraint("attempts BETWEEN 0 AND 3"),
        CheckConstraint("version >= 1"),
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1"),
        Index("ix_audio_transcripts_claim", "tenant_id", "state", "available_at"),
    )


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36))
    report_id: Mapped[str] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(24), default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_id: Mapped[str | None] = mapped_column(String(36))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_error: Mapped[str | None] = mapped_column(String(80))
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "report_id"], ["reports.tenant_id", "reports.id"]),
        UniqueConstraint("tenant_id", "report_id"),
        Index("ix_jobs_claim", "tenant_id", "state", "available_at"),
    )


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(160))
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)


class Dispatch(Base):
    __tablename__ = "dispatches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36))
    case_id: Mapped[str] = mapped_column(String(36))
    team_id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    case_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "case_id"], ["cases.tenant_id", "cases.id"]),
        ForeignKeyConstraint(["tenant_id", "team_id"], ["teams.tenant_id", "teams.id"]),
        UniqueConstraint("tenant_id", "case_id", "case_version"),
    )


class Audit(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    actor_id: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(36))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "case_id"], ["cases.tenant_id", "cases.id"]),
    )


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    public_key: Mapped[str | None] = mapped_column(Text)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class MapLayer(Base):
    __tablename__ = "map_layers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    kind: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(160))
    geojson: Mapped[dict] = mapped_column(JSON)
    provenance: Mapped[str] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewHistory(Base):
    __tablename__ = "review_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36))
    case_id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "case_id"], ["cases.tenant_id", "cases.id"]),
    )


class RetentionPlan(Base):
    __tablename__ = "retention_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="SCHEDULED")
    cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    execute_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[str] = mapped_column(String(40))
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (
        CheckConstraint("status IN ('SCHEDULED','APPROVED','EXECUTED','CANCELLED')"),
        CheckConstraint("execute_after >= cutoff_at"),
        CheckConstraint("approved_by IS NULL OR approved_by <> requested_by"),
    )


class LegalHold(Base):
    __tablename__ = "legal_holds"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    reason_code: Mapped[str] = mapped_column(String(40))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("expires_at > created_at"),)
