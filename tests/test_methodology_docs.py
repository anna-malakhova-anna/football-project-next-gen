import re
from pathlib import Path

from scripts import build_methodology_memo as memo

ROOT = Path(__file__).resolve().parent.parent
HEADINGS = ["What we count, and what we don't", "Who counts as one person", "The counting rules", "Global versus country numbers",
            "How sure are we?", "Privacy by design", "When numbers change", "Known limitations and next steps", "Version and change control"]


def test_the_memo_has_every_section_and_every_counting_rule():
    text = (ROOT / "docs" / "methodology" / "counting-a-participant.md").read_text(encoding="utf-8")
    for i, h in enumerate(HEADINGS, start=1):
        assert f"## {i}. {h}" in text, h
    for n in range(1, 16):
        assert re.search(rf"\| C{n} \|", text), f"C{n}"
    assert "Synthetic data" in text and "not proof of play" in text and "pseudonymous" in text.lower()


def test_the_memo_generator_marks_prose_as_draft_and_formats_years_as_labels():
    assert len(memo.RULES) == 15 and [r[0] for r in memo.RULES] == [f"C{n}" for n in range(1, 16)]
    t = memo.md_table(["Year", "Participants"], [[2025, 3962]])
    assert "| 2025 | 3,962 |" in t
    assert memo.DRAFT == "<!-- DRAFT: Anna to rewrite -->"


def test_the_generator_refuses_to_overwrite_rewritten_prose(tmp_path, monkeypatch):
    out = tmp_path / "memo.md"
    out.write_text("Anna's final prose")
    monkeypatch.setattr(memo, "OUT", out)
    assert memo.main([]) == 1
    assert out.read_text() == "Anna's final prose"


def test_adrs_and_changelog_exist_and_state_the_policy_limits():
    adr = lambda n: (ROOT / "docs" / "decisions" / n).read_text(encoding="utf-8")  # noqa: E731
    assert "traceable" in adr("ADR-005-counting-rules.md").lower() or "C15" in adr("ADR-005-counting-rules.md")
    privacy = adr("ADR-006-privacy-controls.md")
    assert "not legal interpretations" in privacy and "not anonymous" in privacy and "Snowflake mapping" in privacy
    assert "sdcMicro" in privacy and "tau-Argus" in privacy
    publish = adr("ADR-007-publish-and-restatement.md")
    for cause in ("NEW_SOURCE_DATA", "IDENTITY_CHANGE", "METHODOLOGY_CHANGE", "UNKNOWN"):
        assert cause in publish
    assert "v1.0" in (ROOT / "docs" / "methodology" / "CHANGELOG.md").read_text(encoding="utf-8")
