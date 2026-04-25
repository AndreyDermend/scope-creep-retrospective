"""Tests for the role definitions — making sure system prompts carry
the key behavioural instructions."""

from scope_creep.roles import ANDREY, DIMITAR, DR_HONG, SCOPE_DOCUMENT


def test_dr_hong_has_scope_discipline():
    prompt = DR_HONG.system_prompt.lower()
    # Dr. Hong must be about discipline, review, minimum viable
    assert "scope" in prompt
    assert any(word in prompt for word in ("minimum", "trim", "remov"))


def test_andrey_overdelivery_explicit():
    prompt = ANDREY.system_prompt.lower()
    # Andrey must be told to add extras
    assert any(word in prompt for word in ("over-deliver", "over deliver", "extras", "value-adds", "at least three"))
    # And told to return a python fence
    assert "```python" in ANDREY.system_prompt


def test_dimitar_mentions_pptx():
    prompt = DIMITAR.system_prompt.lower()
    assert "python-pptx" in prompt
    assert "retro" in prompt or "scrum" in prompt


def test_scope_document_is_specific():
    doc = SCOPE_DOCUMENT
    assert "prediction.csv" in doc
    assert "Churn" in doc
    assert "LogisticRegression" in doc
    # must have numbered requirements
    assert "1." in doc and "2." in doc


def test_all_roles_have_name_and_prompt():
    for role in (DR_HONG, ANDREY, DIMITAR):
        assert role.name
        assert len(role.system_prompt) > 50
