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
