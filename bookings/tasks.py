import logging
from datetime import timedelta

import resend
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from bookings.models import Booking, EmailLog

logger = logging.getLogger(__name__)


def _send_email(booking, to_email, subject, html, kind):
    if not settings.RESEND_API_KEY:
        EmailLog.objects.create(
            booking=booking,
            restaurant=booking.restaurant if booking else None,
            to_email=to_email,
            subject=subject,
            kind=kind,
            status="failed",
            error_message="Missing RESEND_API_KEY",
        )
        return False
    resend.api_key = settings.RESEND_API_KEY
    try:
        resend.Emails.send(
            {
                "from": settings.FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html,
            }
        )
        EmailLog.objects.create(
            booking=booking,
            restaurant=booking.restaurant if booking else None,
            to_email=to_email,
            subject=subject,
            kind=kind,
            status="sent",
        )
        return True
    except Exception as exc:
        logger.exception("Email send failed")
        EmailLog.objects.create(
            booking=booking,
            restaurant=booking.restaurant if booking else None,
            to_email=to_email,
            subject=subject,
            kind=kind,
            status="failed",
            error_message=str(exc),
        )
        return False


def _receipt_html(title, lines):
    body = "".join(f"<p style='margin:4px 0'>{line}</p>" for line in lines)
    return (
        "<div style='font-family:Courier New,monospace;max-width:520px;margin:0 auto;"
        "border:1px solid #111;padding:16px;background:#fff'>"
        "<p style='margin:0 0 8px 0;font-weight:bold'>SEATED</p>"
        f"<p style='margin:0 0 8px 0'>{title}</p>"
        "<p style='margin:0 0 8px 0'>====================</p>"
        f"{body}"
        "<p style='margin:8px 0 0 0'>====================</p>"
        "<p style='margin:8px 0 0 0'>Managed by Seated</p>"
        "</div>"
    )


@shared_task
def send_reminder_emails():
    tomorrow = timezone.localdate() + timedelta(days=1)
    bookings = Booking.objects.filter(
        date=tomorrow,
        status=Booking.STATUS_CONFIRMED,
        reminder_sent=False,
    ).select_related("restaurant")
    for booking in bookings:
        subject = f"See you tomorrow - {booking.restaurant.name} at {booking.time.strftime('%H:%M')}"
        html = _receipt_html(
            "<h3>SEATED Reminder</h3>",
            [
                f"RESTAURANT {booking.restaurant.name}",
                f"DATE {booking.date}",
                f"TIME {booking.time.strftime('%H:%M')}",
                f"PARTY {booking.party_size}",
                f"Cancel: {settings.SITE_URL}{booking.get_cancel_url()}",
            ],
        )
        if _send_email(booking, booking.guest_email, subject, html, "reminder"):
            booking.reminder_sent = True
            booking.save(update_fields=["reminder_sent"])


@shared_task
def send_confirmation_email(booking_id):
    booking = Booking.objects.select_related("restaurant", "table").get(pk=booking_id)
    subject = f"Your booking at {booking.restaurant.name} - {booking.date} at {booking.time.strftime('%H:%M')}"
    html = _receipt_html(
        "<h3>SEATED Booking Confirmation</h3>",
        [
            f"RESTAURANT {booking.restaurant.name}",
            f"DATE {booking.date}",
            f"TIME {booking.time.strftime('%H:%M')}",
            f"PARTY {booking.party_size}",
            f"REF #{booking.id}",
            booking.restaurant.booking_confirmation_message or "",
            f"Cancel: {settings.SITE_URL}{booking.get_cancel_url()}",
            f"Modify: {settings.SITE_URL}{booking.get_modify_url()}",
        ],
    )
    sent = _send_email(booking, booking.guest_email, subject, html, "confirmation")
    if sent:
        booking.confirmation_sent = True
        booking.save(update_fields=["confirmation_sent"])

    if booking.restaurant.email:
        notification_subject = (
            f"New booking - {booking.guest_name}, {booking.party_size} covers, {booking.date} at {booking.time.strftime('%H:%M')}"
        )
        notification_html = _receipt_html(
            "<h3>SEATED New Booking</h3>",
            [
                f"GUEST {booking.guest_name}",
                f"PARTY {booking.party_size}",
                f"DATE {booking.date}",
                f"TIME {booking.time.strftime('%H:%M')}",
            ],
        )
        _send_email(booking, booking.restaurant.email, notification_subject, notification_html, "restaurant_notification")


@shared_task
def send_cancellation_email(booking_id):
    booking = Booking.objects.select_related("restaurant").get(pk=booking_id)
    subject = f"Booking cancelled - {booking.restaurant.name} - {booking.date} at {booking.time.strftime('%H:%M')}"
    html = _receipt_html(
        "Booking cancellation",
        [
            f"RESTAURANT {booking.restaurant.name}",
            f"DATE {booking.date}",
            f"TIME {booking.time.strftime('%H:%M')}",
            f"PARTY {booking.party_size}",
        ],
    )
    _send_email(booking, booking.guest_email, subject, html, "cancellation")


@shared_task
def mark_completed_bookings():
    yesterday = timezone.localdate() - timedelta(days=1)
    Booking.objects.filter(date=yesterday, status=Booking.STATUS_CONFIRMED).update(status=Booking.STATUS_COMPLETED)
