from app.services.creator_outreach_templates import fill_template, get_template


def test_fill_template_uses_first_name_and_code_hint():
    template = get_template("gifted_collab")
    assert template is not None
    body = fill_template(
        template.body,
        name="Saffiyah Travels",
        handle="@saffiyah.travels",
        code="",
        content_url="https://example.com/post",
    )
    assert "Hi Saffiyah," in body
    assert "SAFFIYAH10" in body
    assert "especially the piece" in body


def test_follow_up_template_exists():
    assert get_template("follow_up") is not None
    assert get_template("missing") is None
