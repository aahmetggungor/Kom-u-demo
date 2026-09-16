from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Source(StrEnum):
    android = "android"
    manual = "manual"
    sms = "sms"
    messaging = "messaging"
    social = "social"
    phone = "phone"


class Coordinates(StrictModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class ReportIn(StrictModel):
    client_id: UUID
    text: str = Field(min_length=1, max_length=8000)
    source: Source = Source.manual
    language: Literal["tr", "el", "en", "und"] = "und"
    occurred_at: datetime
    address_raw: str | None = Field(default=None, max_length=1000)
    location: Coordinates | None = None

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("message cannot be whitespace")
        return value

    @field_validator("occurred_at")
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None:
            raise ValueError("timezone required")
        if value > datetime.now(UTC) + timedelta(minutes=10):
            raise ValueError("timestamp too far in the future")
        return value.astimezone(UTC)


class ReviewIn(StrictModel):
    expected_version: int = Field(ge=1)
    verification_status: Literal["VERIFIED", "REJECTED", "UNVERIFIED"]
    urgency_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    location: Coordinates | None = None
    confirm_location: bool = False
    region: str | None = Field(default=None, max_length=160)
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def confirmation(self):
        if self.confirm_location and self.location is None:
            raise ValueError("explicit coordinates required for confirmation")
        if not self.reason.strip():
            raise ValueError("reason required")
        return self


class DispatchIn(StrictModel):
    expected_version: int = Field(ge=1)
    team_id: UUID


class TeamIn(StrictModel):
    name: str = Field(min_length=1, max_length=160)


class MergeIn(StrictModel):
    target_case_id: UUID
    expected_source_version: int = Field(ge=1)
    expected_target_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


class SplitIn(StrictModel):
    expected_version: int = Field(ge=1)
    report_ids: list[UUID] = Field(min_length=1, max_length=99)
    reason: str = Field(min_length=3, max_length=500)


class ReportAccepted(StrictModel):
    report_id: str
    case_id: str
    processing_status: str
    replayed: bool


class AudioMetadata(StrictModel):
    id: str
    report_id: str
    state: Literal["QUARANTINED", "SCAN_PASSED", "SCAN_ERROR", "RELEASED", "REJECTED"]
    content_type: Literal["audio/wav"]
    plaintext_bytes: int = Field(ge=1, le=2_000_000)
    duration_ms: int = Field(ge=200, le=30_000)
    encryption_key_id: str = Field(min_length=1, max_length=80)
    version: int = Field(ge=1)
    scanner_revision: str | None = Field(default=None, max_length=160)
    scan_verdict: Literal["CLEAN", "MALICIOUS", "INVALID", "ERROR"] | None = None
    scan_reason_code: str | None = Field(default=None, max_length=80)
    scanned_at: datetime | None = None
    decision_reason: str | None = Field(default=None, max_length=500)
    decided_at: datetime | None = None
    created_at: datetime
    human_review_required: Literal[True]


class AudioAccepted(AudioMetadata):
    replayed: bool


class AudioDecisionIn(StrictModel):
    expected_version: int = Field(ge=1)
    decision: Literal["RELEASE", "REJECT"]
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value):
        if not value.strip():
            raise ValueError("reason required")
        return value.strip()


class TranscriptReviewIn(StrictModel):
    expected_version: int = Field(ge=1)
    corrected_text: str = Field(min_length=1, max_length=8000)
    language: Literal["tr", "el", "en", "und"]
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("corrected_text", "reason")
    @classmethod
    def nonblank_transcript_value(cls, value):
        if not value.strip():
            raise ValueError("value cannot be blank")
        return value.strip()


class RetentionScheduleIn(StrictModel):
    cutoff_at: datetime
    execute_after: datetime
    reason_code: Literal["INCIDENT_ENDED", "RETENTION_EXPIRED", "DATA_SUBJECT_REQUEST"]

    @model_validator(mode="after")
    def bounded_times(self):
        if self.cutoff_at.tzinfo is None or self.execute_after.tzinfo is None:
            raise ValueError("timezone required")
        now = datetime.now(UTC)
        self.cutoff_at = self.cutoff_at.astimezone(UTC)
        self.execute_after = self.execute_after.astimezone(UTC)
        if self.cutoff_at > now:
            raise ValueError("cutoff cannot be in the future")
        if self.execute_after < now:
            raise ValueError("execution cannot be scheduled in the past")
        if self.execute_after < self.cutoff_at:
            raise ValueError("execution must follow cutoff")
        return self


class RetentionApproveIn(StrictModel):
    expected_status: Literal["SCHEDULED"]
    acknowledge_irreversible_purge: Literal[True]


class RetentionCancelIn(StrictModel):
    expected_status: Literal["SCHEDULED", "APPROVED"]
    reason_code: Literal["PLAN_REPLACED", "INCIDENT_REOPENED", "ENTERED_IN_ERROR"]


class LegalHoldIn(StrictModel):
    reason_code: Literal["LITIGATION", "REGULATOR_REQUEST", "SECURITY_INVESTIGATION"]
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def future_expiry(cls, value):
        if value.tzinfo is None:
            raise ValueError("timezone required")
        value = value.astimezone(UTC)
        if value <= datetime.now(UTC):
            raise ValueError("legal hold expiry must be in the future")
        if value > datetime.now(UTC) + timedelta(days=3660):
            raise ValueError("legal hold expiry must be reviewed within ten years")
        return value


class LegalHoldReleaseIn(StrictModel):
    expected_active: Literal[True]
    reason_code: Literal["HOLD_ENDED", "ENTERED_IN_ERROR"]
