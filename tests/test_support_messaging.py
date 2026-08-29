"""Tests for support email threading."""

from app.services.support_messaging import (
    build_thread_subject,
    parse_ticket_number,
    ticket_subject_tag,
)


def test_parse_ticket_number_from_subject():
    assert parse_ticket_number("Re: [TCK-AB12CD34] Install help") == "TCK-AB12CD34"
    assert parse_ticket_number("No ticket here") is None


def test_ticket_subject_tag():
    assert ticket_subject_tag("TCK-AB12CD34") == "[TCK-AB12CD34]"


def test_build_thread_subject_reply():
    class Ticket:
        ticket_number = "TCK-TEST01"
        subject = "QR code missing"

    subject = build_thread_subject(Ticket(), is_reply=True)
    assert "[TCK-TEST01]" in subject
    assert "QR code missing" in subject
