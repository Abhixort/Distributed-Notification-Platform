import pytest
from app.services.template_service import template_service


def test_template_rendering_valid_context():
    subject_tmpl = "Hello {{ name }}!"
    body_tmpl = "<p>Your code is {{ code }}. Valid until {{ expiry }}.</p>"
    data = {"name": "Alice", "code": "984210", "expiry": "10 mins"}

    subj, body = template_service.render_content(
        body_template=body_tmpl,
        subject_template=subject_tmpl,
        data=data,
    )

    assert subj == "Hello Alice!"
    assert body == "<p>Your code is 984210. Valid until 10 mins.</p>"


def test_template_rendering_missing_optional_subject():
    body_tmpl = "Order #{{ id }} confirmed"
    subj, body = template_service.render_content(
        body_template=body_tmpl,
        subject_template=None,
        data={"id": "99"},
    )
    assert subj is None
    assert body == "Order #99 confirmed"
