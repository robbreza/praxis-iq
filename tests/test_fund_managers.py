"""Pin the prospectus PM extractor (core.fund_managers.parse_managers) — the SOURCE half of PM
rostering. Pure (no network): asserts it pulls clean person names from the common '40-Act prospectus
phrasings, dedupes nickname/format variants, keeps two same-surname PMs (a father/son pair) apart,
and REJECTS fund/entity names rather than emitting a wrong contact."""
from core.fund_managers import parse_managers, _clean_name, extract_text

# Modeled on a real Heartland 485BPOS: three fund teams (one PM shared), nickname parentheticals,
# formal middle initials, and a same-surname pair with different middle initials (R vs J).
FIXTURE = (
    "The Mid Cap Value Fund is managed by a team of investment professionals, which consists of "
    'Colin P. McWey, William ("Will") R. Nasgovitz and Troy W. McGlone . '
    "Mr. McWey, CFA, has served as a Portfolio Manager of the Mid Cap Value Fund since October 2014. "
    "Mr. McWey is a Vice President and Portfolio Manager with the Adviser. "
    "The Value Plus Fund is managed by a team of investment professionals, which consists of "
    "Andrew J. Fleming, Michael J. Warecki and Jacob S. Westphal . "
    'The Value Fund is co-managed by William ("Bill") J. Nasgovitz and Michael J. Warecki . '
    "Mr. Fleming is a Vice President and Portfolio Manager with the Adviser."
)


def test_parse_managers_clean_roster():
    pms = parse_managers(FIXTURE)
    names = [p["name"] for p in pms]
    for expected in ("Colin P. McWey", "Troy W. McGlone", "Andrew J. Fleming",
                     "Michael J. Warecki", "Jacob S. Westphal"):
        assert expected in names, (expected, names)
    # same-surname father/son kept apart by middle initial
    assert "William R. Nasgovitz" in names and "William J. Nasgovitz" in names
    # deduped (Warecki appears in two fund teams; McWey formal vs any nickname)
    assert len(names) == len(set(names))
    assert names.count("Michael J. Warecki") == 1
    # never a fund/entity name as a person
    assert all("Fund" not in n and "Adviser" not in n for n in names)
    # every PM carries a title (defaults to the role we know)
    assert all(p["title"] for p in pms)


def test_clean_name_accepts_people_rejects_entities():
    assert _clean_name("Colin P. McWey") == "Colin P. McWey"
    assert _clean_name("Mr. Andrew J. Fleming, CFA") == "Andrew J. Fleming"
    assert _clean_name('William ("Will") R. Nasgovitz') == "William R. Nasgovitz"
    # entities / fund names / run-ons -> None
    assert _clean_name("Value Plus Fund") is None
    assert _clean_name("Heartland Advisors LLC") is None
    assert _clean_name("the Adviser") is None
    assert _clean_name("A B") is None                    # initials-only junk


def test_extract_text_strips_markup():
    out = extract_text("<p>Colin&#160;P.&#160;McWey <b>is a PM</b></p>")
    assert "<" not in out and ">" not in out
    assert "Colin P. McWey" in out


def test_empty_and_no_match_return_empty():
    assert parse_managers("") == []
    assert parse_managers("This prospectus discusses fees and risks only.") == []


# ── LLM fallback ──────────────────────────────────────────────────────────────
import core.fund_managers as FM


def test_parse_llm_array_validates_and_dedupes():
    # fenced JSON, a real PM, a hallucinated fund name (must be dropped), and a duplicate
    raw = (
        "```json\n"
        '[{"name": "Gregory J. Cheng", "title": "Portfolio Manager"},'
        ' {"name": "Global Growth Fund", "title": "Portfolio Manager"},'
        ' {"name": "Mr. Gregory J. Cheng", "title": "Managing Partner"},'
        ' {"name": "Ana R. Fuentes", "title": "Senior Analyst and Portfolio Manager"}]\n'
        "```")
    rows = FM._parse_llm_array(raw)
    names = [r["name"] for r in rows]
    assert "Gregory J. Cheng" in names and "Ana R. Fuentes" in names
    assert "Global Growth Fund" not in names          # entity name rejected
    assert names.count("Gregory J. Cheng") == 1        # honorific variant deduped


def test_llm_extract_uses_claude_and_guards(monkeypatch):
    src = ("MANAGEMENT OF THE FUND. Dana K. Reeves has served as a Portfolio Manager since 2019. "
           "The Fund is managed by the team.")
    monkeypatch.setattr(FM, "_claude", lambda prompt, **k:
                        '[{"name":"Dana K. Reeves","title":"Portfolio Manager"},'
                        ' {"name":"Acme Trust","title":"Portfolio Manager"}]')
    out = FM._llm_extract(src)
    assert [r["name"] for r in out] == ["Dana K. Reeves"]     # fund/trust filtered out


def test_llm_extract_grounds_out_hallucinations(monkeypatch):
    # a plausible-looking name NOT present in the source must be dropped (never-guess rule)
    src = "MANAGEMENT OF THE FUND. Dana K. Reeves has served as a Portfolio Manager since 2019."
    monkeypatch.setattr(FM, "_claude", lambda prompt, **k:
                        '[{"name":"Ghost X. Person","title":"Portfolio Manager"},'
                        ' {"name":"Dana K. Reeves","title":"Portfolio Manager"}]')
    assert [r["name"] for r in FM._llm_extract(src)] == ["Dana K. Reeves"]


def test_llm_extract_handles_bad_output(monkeypatch):
    monkeypatch.setattr(FM, "_claude", lambda prompt, **k: None)          # no key / no network
    assert FM._llm_extract("Portfolio Manager text") == []
    monkeypatch.setattr(FM, "_claude", lambda prompt, **k: "not json at all")
    assert FM._llm_extract("Portfolio Manager text") == []


def test_pm_window_bounds_to_named_section():
    head = "Fees and expenses. " * 400
    body = ("The Fund is managed by a team which consists of Dana K. Reeves, who has served as a "
            "Portfolio Manager since 2019. ")
    win = FM._pm_window(head + body + ("More risk disclosure. " * 4000), size=2000)
    assert "Dana K. Reeves" in win and len(win) <= 2000
