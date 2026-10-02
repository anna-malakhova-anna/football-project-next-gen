"""Guards against drift between what the generators emit and what the dbt seeds map."""
import csv
from pathlib import Path

from generator.sources import ca_club, intl_federation as intl, us_league

SEEDS = Path(__file__).resolve().parent.parent / "dbt" / "seeds"


def _read(name):
    with open(SEEDS / f"{name}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_division_map_covers_every_generated_label():
    got = {(r["source_system"], r["source_label"]): r["canonical_division"] for r in _read("division_map")}
    for canon, labels in {**us_league.YOUTH_LABELS, **us_league.ADULT_LABELS}.items():
        for l in labels:
            assert got[("US_LEAGUE", l)] == canon
    for _, _, opts in ca_club.YOUTH_PROGRAMS:
        for l in opts:
            assert got[("CA_CLUB", l)] == opts[2]
    for canon, opts in ca_club.ADULT_PROGRAMS.items():
        for l in opts:
            assert got[("CA_CLUB", l)] == canon
    for labels in intl.CATEGORY_LABELS.values():
        for canon, l in labels.items():
            assert got[("INTL_FED", l)] == canon


def test_country_and_gender_maps_cover_generated_values():
    countries = {r["source_value"].lower(): r["country_code"] for r in _read("country_map")}
    for code, forms in intl.COUNTRY_ALT.items():
        for v in [intl.ISO3[code], *forms]:
            assert countries[v.lower()] == code
    genders = {r["source_value"].lower(): r["sex_code"] for r in _read("gender_map")}
    for male, female in us_league.GENDER_STYLES:          # US styles are (M, F)
        assert genders[male.lower()] == "M" and genders[female.lower()] == "F"
    for female, male in intl.GENDER_LABELS.values():      # intl labels are (F, M)
        assert genders[male.lower()] == "M" and genders[female.lower()] == "F"
    assert genders["female"] == "F" and genders["male"] == "M"
