import asyncio
import smtplib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Protocol

import httpx
from sqlmodel import Session, select

from app.core.config import Settings
from app.models import AlertDelivery, Assignment, Course

ALERT_THRESHOLDS: tuple[tuple[str, timedelta], ...] = (
    ("3h", timedelta(hours=3)),
    ("24h", timedelta(hours=24)),
    ("3d", timedelta(days=3)),
    ("7d", timedelta(days=7)),
)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@dataclass(frozen=True)
class AlertMessage:
    assignment_id: int
    assignment_name: str
    course_name: str
    due_at: datetime
    alert_level: str
    status: str

    @property
    def text(self) -> str:
        remaining = _as_utc(self.due_at) - datetime.now(UTC)
        hours = max(0, int(remaining.total_seconds() // 3600))
        return (
            f"DDL提醒 [{self.alert_level}] {self.course_name} / {self.assignment_name} "
            f"将在约 {hours} 小时后截止。当前状态：{self.status}。"
        )


class AlertNotifier(Protocol):
    channel: str

    async def send(self, message: AlertMessage) -> None: ...


class NoopNotifier:
    channel = "noop"

    async def send(self, message: AlertMessage) -> None:
        return None


class WebhookNotifier:
    channel = "webhook"

    def __init__(self, url: str, *, kind: str = "generic", client: httpx.AsyncClient | None = None):
        self.url = url
        self.kind = kind
        self.client = client

    def _payload(self, message: AlertMessage) -> dict[str, str]:
        if self.kind == "telegram":
            return {"text": message.text}
        return {"content": message.text}

    async def send(self, message: AlertMessage) -> None:
        if self.client is not None:
            response = await self.client.post(self.url, json=self._payload(message))
        else:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(self.url, json=self._payload(message))
        response.raise_for_status()


class EmailNotifier:
    channel = "email"

    def __init__(
        self,
        *,
        smtp_host: str,
        smtp_port: int,
        sender: str,
        recipient: str,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender = sender
        self.recipient = recipient
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def _send_sync(self, message: AlertMessage) -> None:
        email = EmailMessage()
        email["Subject"] = f"Academic OS DDL提醒：{message.assignment_name}"
        email["From"] = self.sender
        email["To"] = self.recipient
        email.set_content(message.text)
        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as smtp:
            if self.use_tls:
                smtp.starttls()
            if self.username and self.password:
                smtp.login(self.username, self.password)
            smtp.send_message(email)

    async def send(self, message: AlertMessage) -> None:
        await asyncio.to_thread(self._send_sync, message)


def alert_level_for(due_at: datetime, *, now: datetime) -> str | None:
    remaining = _as_utc(due_at) - _as_utc(now)
    if remaining <= timedelta(0):
        return None
    for level, threshold in ALERT_THRESHOLDS:
        if remaining <= threshold:
            return level
    return None


def make_notifier(settings: Settings) -> AlertNotifier:
    if settings.alert_webhook_url:
        return WebhookNotifier(settings.alert_webhook_url, kind=settings.alert_webhook_kind)
    return NoopNotifier()


async def dispatch_due_alerts(
    session: Session,
    notifier: AlertNotifier,
    *,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(UTC)
    assignments = session.exec(
        select(Assignment, Course)
        .join(Course, Course.id == Assignment.course_id)
        .where(Assignment.due_at.is_not(None))
        .where(Assignment.submission_status.in_(["unsubmitted", "overdue"]))
    ).all()
    sent = 0
    for assignment, course in assignments:
        assert assignment.id is not None
        assert assignment.due_at is not None
        level = alert_level_for(assignment.due_at, now=now)
        if level is None:
            continue
        dedupe_key = (
            f"assignment:{assignment.canvas_id}:due:{assignment.due_at.isoformat()}:level:{level}"
        )
        delivery = session.exec(
            select(AlertDelivery).where(AlertDelivery.dedupe_key == dedupe_key)
        ).first()
        if delivery is not None and delivery.status == "sent":
            continue
        if delivery is None:
            delivery = AlertDelivery(
                assignment_id=assignment.id,
                alert_level=level,
                channel=notifier.channel,
                dedupe_key=dedupe_key,
            )
            session.add(delivery)
            session.flush()
        message = AlertMessage(
            assignment_id=assignment.id,
            assignment_name=assignment.name,
            course_name=course.name,
            due_at=assignment.due_at,
            alert_level=level,
            status=assignment.submission_status,
        )
        try:
            await notifier.send(message)
        except Exception as exc:  # Persist failure for diagnostics and retry next run.
            delivery.status = "failed"
            delivery.error = str(exc)[:500]
        else:
            delivery.status = "sent"
            delivery.sent_at = now
            delivery.error = None
            sent += 1
        delivery.updated_at = now
        session.commit()
    return sent
