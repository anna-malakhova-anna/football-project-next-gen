"""Builds the SYNTHETIC true-person registry and the participation plan.

Everything here is fake. The registry is ground truth: it is written to
data/ground_truth/ and never loaded into the raw schema.

Two outputs:
  * registry:       one row per true person (hidden `true_person_id`)
  * participations: one row per planned registration (person x season x term x league slot).
                    Source generators turn these into source records, so a person's
                    behaviour (churn, moves, multi-league play) is decided exactly once.
"""
from __future__ import annotations

import datetime as dt
import os
import random
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from faker import Faker

from generator.draw_order import country_key

from generator import markets as markets_mod
from text_unidecode import unidecode

SOURCE_BY_COUNTRY = {"US": "US_LEAGUE", "CA": "CA_CLUB"}  # anything else -> INTL_FED

NICKNAMES = {
    "F": {
        "Elizabeth": "Liz", "Katherine": "Kate", "Jennifer": "Jen", "Samantha": "Sam",
        "Madison": "Maddie", "Abigail": "Abby", "Isabella": "Izzy", "Margaret": "Maggie",
        "Rebecca": "Becca", "Victoria": "Tori", "Gabriella": "Gabby", "Natalie": "Nat",
        "Alexandra": "Alex", "Olivia": "Liv", "Charlotte": "Charlie", "Stephanie": "Steph",
    },
    "M": {
        "Robert": "Bob", "William": "Bill", "Michael": "Mike", "Christopher": "Chris",
        "Matthew": "Matt", "Alexander": "Alex", "Joseph": "Joe", "Benjamin": "Ben",
        "Nicholas": "Nick", "Jacob": "Jake", "Daniel": "Danny", "Thomas": "Tom",
        "Anthony": "Tony", "Zachary": "Zach", "Samuel": "Sam", "Jonathan": "Jon",
    },
}
NICKNAME_LOCALES = {"en_US", "en_CA", "en_GB"}

# (state, 3-digit zip prefix range, weight). NJ/MA/CT zips start with 0 (leading-zero defect).
US_REGIONS = [
    ("TX", (750, 799), 14), ("CA", (900, 961), 14), ("FL", (320, 349), 10), ("NJ", (70, 89), 8),
    ("MA", (10, 27), 7), ("NY", (100, 149), 9), ("IL", (600, 629), 7), ("OH", (430, 458), 6),
    ("WA", (980, 994), 5), ("GA", (300, 319), 6), ("CO", (800, 816), 4), ("AZ", (850, 865), 4),
    ("PA", (150, 196), 4), ("CT", (60, 69), 2),
]
# province -> first letters of postal codes
CA_POSTAL_LETTERS = {
    "QC": "HGJ", "ON": "KLMNP", "NB": "E", "BC": "V", "AB": "T", "NS": "B", "MB": "R",
}
CA_FR_REGIONS = [("QC", 70), ("NB", 15), ("ON", 15)]
CA_EN_REGIONS = [("ON", 45), ("BC", 20), ("AB", 20), ("NS", 8), ("MB", 7)]

INTL_LANG = {"MX": "es", "GB": "en", "JP": "ja", "DE": "de", "AT": "de", "ES": "es"}
INTL_PHONE_PREFIX = {"MX": ("+52", 10), "GB": ("+44", 10), "JP": ("+81", 10),
                     "DE": ("+49", 10), "AT": ("+43", 10), "ES": ("+34", 8)}  # Spain: 8 digits (Panama's length) so the renamed population draws the same numbers
EMAIL_DOMAINS = ["example.com", "example.org", "example.net"]  # reserved, never real inboxes

REGISTRY_FIELDS = [
    "true_person_id", "segment", "household_id", "given_name", "family_name", "nickname",
    "dob", "sex", "home_country", "home_region", "postal_code", "language", "is_minor",
    "guardian_name", "guardian_email", "guardian_phone", "own_email", "own_phone",
    "marketing_opt_in", "photo_consent", "first_season", "last_season",
    "is_cross_border", "alt_country", "alt_region", "switch_season", "is_multi_league",
    "twin_group_id", "name_change_season", "later_family_name", "dual_country_year", "home_market_id", "market_launch_year", "alt_market_id",
]
PARTICIPATION_FIELDS = [
    "true_person_id", "source_system", "country_code", "region_code",
    "season_year", "season_term", "league_slot",
]


# The tests would otherwise write the whole 15,000-person dataset, with its million-line fan stream, in almost every test module.
# FLAG_SMALL_POPULATION=1 (set by tests/conftest.py) shrinks the population and the fan stream: the structure, defects and truth files
# are the same, only the sizes are smaller. `load_config(small=...)` overrides the variable for one call.
SMALL_POPULATION_ENV = "FLAG_SMALL_POPULATION"
SMALL_RUN = {"total_people": 4000, "fan_base_events_per_month": 0.3, "fan_stock_penetration": 0.001}


def load_config(path: str | Path = "config/generation.yaml", small: bool | None = None) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    if small is None:
        small = os.environ.get(SMALL_POPULATION_ENV) == "1"
    if small:
        cfg["population"]["total_people"] = SMALL_RUN["total_people"]
        cfg["sources"]["fan"]["base_events_per_month"] = SMALL_RUN["fan_base_events_per_month"]
        cfg["sources"]["fan"]["account"]["stock_penetration"] = SMALL_RUN["fan_stock_penetration"]      # the opening stock of fan accounts is most of the generator's memory
    return cfg


def random_us_zip(rng: random.Random, state: str) -> str:
    lo, hi = next(r for st, r, _ in US_REGIONS if st == state)
    return f"{rng.randint(lo, hi):03d}{rng.randint(0, 99):02d}"


def random_ca_postal(rng: random.Random, province: str) -> str:
    letter = lambda: rng.choice("ABCEGHJKLMNPRSTVXY")  # noqa: E731
    first = rng.choice(CA_POSTAL_LETTERS[province])
    return f"{first}{rng.randint(0, 9)}{letter()} {rng.randint(0, 9)}{letter()}{rng.randint(0, 9)}"


class _Names:
    """Locale-aware name factory; one seeded Faker per locale."""

    def __init__(self, seed: int):
        self._fakers: dict[str, Faker] = {}
        self._seed = seed

    def _fk(self, locale: str) -> Faker:
        if locale not in self._fakers:
            fk = Faker(locale)
            fk.seed_instance(self._seed + sum(map(ord, locale)))
            self._fakers[locale] = fk
        return self._fakers[locale]

    def given(self, locale: str, sex: str) -> str:
        fk = self._fk(locale)
        if locale == "ja_JP":
            return fk.first_romanized_name_female() if sex == "F" else fk.first_romanized_name_male()
        return fk.first_name_female() if sex == "F" else fk.first_name_male()

    def family(self, locale: str) -> str:
        fk = self._fk(locale)
        return fk.last_romanized_name() if locale == "ja_JP" else fk.last_name()


class _Builder:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.pop = cfg["population"]
        self.part = cfg["participation"]
        self.years = cfg["seasons"]["years"]
        self.rng = random.Random(cfg["seed"])
        self.names = _Names(cfg["seed"])
        self.used_phones: set[str] = set()
        self.used_emails: set[str] = set()
        self._hh_counter = 0
        self.markets = markets_mod.build_markets(cfg)["markets"]

    # ---------- small helpers ----------
    def _weighted(self, pairs):
        return self.rng.choices(pairs, weights=[p[-1] for p in pairs])[0]

    def _phone(self, country: str) -> str:
        r = self.rng
        while True:
            if country in ("US", "CA"):
                area = f"{r.randint(2, 9)}{r.randint(0, 9)}{r.randint(0, 9)}"
                if area[1:] == "11":
                    continue
                num = f"+1{area}55501{r.randint(0, 99):02d}"  # 555-01xx is the fictional range
            else:
                prefix, n = INTL_PHONE_PREFIX[country]
                num = prefix + "".join(str(r.randint(0, 9)) for _ in range(n))
            if num not in self.used_phones:
                self.used_phones.add(num)
                return num

    def _email(self, given: str, family: str) -> str:
        base = f"{unidecode(given)}.{unidecode(family)}".lower().replace(" ", "").replace("'", "")
        while True:
            e = f"{base}{self.rng.randint(1, 9999)}@{self.rng.choice(EMAIL_DOMAINS)}"
            if e not in self.used_emails:
                self.used_emails.add(e)
                return e

    def _dob(self, birth_year: int) -> dt.date:
        start = dt.date(birth_year, 1, 1)
        days = (dt.date(birth_year, 12, 31) - start).days
        return start + dt.timedelta(days=self.rng.randint(0, days))

    def _market_for(self, country: str, region: str | None = None, by_year: int | None = None) -> dict:
        """A launched market in `country` (optionally in `region`), weighted by its synthetic household population. Never-launched markets are never chosen."""
        by_year = markets_mod.last_year(self.cfg) if by_year is None else by_year
        pool = markets_mod.launched(self.markets, country, by_year)
        if region is not None:
            pool = [m for m in pool if m["region_code"] == region] or pool
        return self.rng.choices(pool, weights=[m["household_population"] for m in pool])[0]

    def _place(self, country: str, francophone: bool, by_year: int | None = None):
        """-> (region, postal_code, market). The market is chosen first (weighted by its household population, among markets launched by `by_year`), then a postal
        prefix inside it."""
        if country == "US":
            region = self._weighted(US_REGIONS)[0]
            market = self._market_for("US", region, by_year)
            return market["region_code"], f"{self.rng.choice(market['_prefixes'])}{self.rng.randint(0, 99):02d}", market
        if country == "CA":
            region = self._weighted(CA_FR_REGIONS if francophone else CA_EN_REGIONS)[0]
            market = self._market_for("CA", region, by_year)
            letter = lambda: self.rng.choice("ABCEGHJKLMNPRSTVXY")  # noqa: E731
            fsa = self.rng.choice(market["_prefixes"])
            return market["region_code"], f"{fsa} {self.rng.randint(0, 9)}{letter()}{self.rng.randint(0, 9)}", market
        market = self._market_for(country, None, by_year)
        return None, None, market

    def _first_season(self, birth_year: int | None, sex: str, adult: bool, launch_year: int = 0) -> int:
        """Pick a first season; youth are constrained so age at first season is 5-17, and nobody registers before their market's launch year."""
        lo, hi = self.pop["youth_age_range"]
        allowed = [y for y in self.years if y >= launch_year]
        if not adult:
            allowed = [y for y in allowed if lo <= y - birth_year <= hi]
        w = self.part["first_season_weights"]
        mult = self.part["girls_new_player_multiplier"]
        weights = [w[y] * (mult[y] if sex == "F" else 1.0) for y in allowed]
        return self.rng.choices(allowed, weights=weights)[0]

    # ---------- people ----------
    def _p_multi_household(self) -> float:
        """Probability a youth household has 2+ children (solved from the sibling-share target)."""
        hh = self.pop["household"]
        target, max_sib = hh["youth_with_sibling_share"], hh["max_siblings"]
        mean_multi = (2 * 0.8 + 3 * 0.2) if max_sib >= 3 else 2.0
        return target / (mean_multi * (1 - target) + target)

    def _make_twins(self, lead: dict, other: dict, loc: str):
        """Turn `other` into lead's twin: same DOB, season, household; different first name."""
        for _ in range(50):
            given = self.names.given(loc, other["sex"])
            if given.lower() != lead["given_name"].lower():
                break
        other["given_name"], other["nickname"] = given, None
        other["dob"], other["first_season"] = lead["dob"], lead["first_season"]
        gid = f"T{lead['_hh']}"
        lead["twin_group_id"] = other["twin_group_id"] = gid

    def _household_sizes(self, n_youth: int) -> list[int]:
        """Household sizes summing to n_youth; sized so ~30% of youth have a sibling."""
        hh = self.pop["household"]
        target, max_sib = hh["youth_with_sibling_share"], hh["max_siblings"]
        sizes_multi = list(range(2, max_sib + 1))
        mean_multi = (2 * 0.8 + 3 * 0.2) if max_sib >= 3 else 2.0
        # p = prob a household is multi-child, solved from share = p*m / (p*m + 1 - p)
        p = target / (mean_multi * (1 - target) + target)
        sizes: list[int] = []
        total = 0
        while total < n_youth:
            if self.rng.random() < p:
                k = 2 if (max_sib < 3 or self.rng.random() < 0.8) else 3
                k = min(k, sizes_multi[-1])
            else:
                k = 1
            k = min(k, n_youth - total)
            sizes.append(k)
            total += k
        return sizes

    def _sibling_birth_years(self, k: int, lo_by: int, hi_by: int) -> list[int]:
        """k birth years in [lo_by, hi_by] within ~5 years of each other (twins allowed)."""
        r = self.rng
        base = r.randint(lo_by, hi_by)
        years = [base]
        for _ in range(k - 1):
            for _try in range(50):
                y = base + r.randint(-5, 5)
                if lo_by <= y <= hi_by:
                    years.append(y)
                    break
            else:
                years.append(base)
        return years

    def _youth_household(self, country: str, k: int, ca_fr: bool | None = None):
        r = self.rng
        ylo, yhi = self.pop["youth_age_range"]
        francophone = bool(ca_fr)
        if country == "CA" and ca_fr is None:
            francophone = r.random() < self.pop["ca_francophone_share"]
        loc = self._locale(country, francophone)
        region, postal, market = self._place(country, francophone)
        # birth years: a child must be 5 to 17 in at least one season on or after the market's launch year
        lo_by, hi_by = max(min(self.years), market["launch_year"]) - yhi, max(self.years) - ylo
        family = self.names.family(loc)
        g_sex = r.choice(["F", "M"])
        g_given = self.names.given(loc, g_sex)
        g_family = family if r.random() < 0.85 else self.names.family(loc)
        guardian = {
            "guardian_name": f"{g_given} {g_family}",
            "guardian_email": self._email(g_given, g_family),
            "guardian_phone": self._phone(country),
        }
        self._hh_counter += 1
        kids = []
        for by in self._sibling_birth_years(k, lo_by, hi_by):
            kids.append(self._person(loc, country, region, postal, family, by,
                                     francophone, minor=True, guardian=guardian,
                                     hh_key=self._hh_counter, market=market))
        twin_share = self.pop.get("twins", {}).get("household_share", 0)
        if k >= 2 and r.random() < twin_share / self._p_multi_household():
            self._make_twins(kids[0], kids[1], loc)
        return kids

    def _locale(self, country: str, francophone: bool = False) -> str:
        if country == "US":
            return self.pop["locales"]["US"]
        if country == "CA":
            return self.pop["locales"]["CA_FR" if francophone else "CA_EN"]
        return self.pop["locales"][country]

    def _language(self, country: str, francophone: bool) -> str:
        if country == "CA":
            return "fr" if francophone else "en"
        return "en" if country == "US" else INTL_LANG[country]

    def _person(self, loc, country, region, postal, family, birth_year, francophone,
                minor, guardian=None, sex=None, hh_key=None, market=None):
        r = self.rng
        if sex is None:
            share = self.pop["youth_female_share"] if minor else self.pop["adult_female_share"]
            sex = "F" if r.random() < share else "M"
        nickname = None
        if loc in NICKNAME_LOCALES and r.random() < self.pop["nickname_share"]:
            given = r.choice(sorted(NICKNAMES[sex]))
            nickname = NICKNAMES[sex][given]
        else:
            given = self.names.given(loc, sex)
        dob = self._dob(birth_year)
        first = self._first_season(birth_year, sex, adult=not minor, launch_year=market["launch_year"])
        c = self.pop["consent"]
        p = {
            "segment": None, "household_id": None,
            "given_name": given, "family_name": family, "nickname": nickname,
            "dob": dob, "sex": sex, "home_country": country, "home_region": region,
            "postal_code": postal, "language": self._language(country, francophone),
            "is_minor": minor,
            "guardian_name": None, "guardian_email": None, "guardian_phone": None,
            "own_email": None, "own_phone": None,
            "marketing_opt_in": r.random() < c["marketing_opt_in_rate"],
            "photo_consent": r.random() < c["photo_consent_rate"],
            "first_season": first, "last_season": None,
            "is_cross_border": False, "alt_country": None, "alt_region": None,
            "switch_season": None, "is_multi_league": False,
            "twin_group_id": None, "name_change_season": None, "later_family_name": None,
            "dual_country_year": None,
            "home_market_id": market["market_id"], "market_launch_year": market["launch_year"], "alt_postal": None, "alt_market_id": None,
            "_hh": hh_key,
        }
        if minor:
            p.update(guardian)
        else:
            p["own_email"] = self._email(given, family)
            p["own_phone"] = self._phone(country)
        return p

    def _adult(self, country: str):
        r = self.rng
        francophone = country == "CA" and r.random() < self.pop["ca_francophone_share"]
        loc = self._locale(country, francophone)
        region, postal, market = self._place(country, francophone)
        alo = self.pop["adult_age_range"][0]
        sex = "F" if r.random() < self.pop["adult_female_share"] else "M"
        # DOB is re-derived in _fix_adult_first_seasons once first_season is known
        return self._person(loc, country, region, postal, self.names.family(loc),
                            min(self.years) - alo, francophone, minor=False, sex=sex, market=market)

    def build_people(self):
        r = self.rng
        n = self.pop["total_people"]
        seg = self.pop["segments"]
        n_us = round(n * seg["us_youth"])
        n_ca = round(n * seg["ca_youth"])
        n_intl = round(n * seg["intl"])
        n_adult = n - n_us - n_ca - n_intl
        people: list[dict] = []

        for country, count, segname in (("US", n_us, "US_YOUTH"), ("CA", n_ca, "CA_YOUTH")):
            for k in self._household_sizes(count):
                for p in self._youth_household(country, k):
                    p["segment"] = segname
                    people.append(p)

        # International: adults are individuals, youth come in households
        shares = self.pop["intl_country_shares"]
        countries = sorted(shares, key=country_key)
        n_intl_adult = round(n_intl * self.pop["intl_adult_share"])
        for _ in range(n_intl_adult):
            c = r.choices(countries, weights=[shares[x] for x in countries])[0]
            p = self._adult(c)
            p["segment"] = "INTL"
            people.append(p)
        intl_youth_by_country: dict[str, int] = {}
        for _ in range(n_intl - n_intl_adult):
            c = r.choices(countries, weights=[shares[x] for x in countries])[0]
            intl_youth_by_country[c] = intl_youth_by_country.get(c, 0) + 1
        for c in sorted(intl_youth_by_country, key=country_key):
            for k in self._household_sizes(intl_youth_by_country[c]):
                for p in self._youth_household(c, k):
                    p["segment"] = "INTL"
                    people.append(p)

        for _ in range(n_adult):
            c = "US" if r.random() < self.pop["us_adult_share_of_adults_us_ca"] else "CA"
            p = self._adult(c)
            p["segment"] = "ADULT_US_CA"
            people.append(p)

        self._fix_adult_first_seasons(people)
        self._designate_movers(people)
        self._flag_multi_league(people)
        return people

    def _fix_adult_first_seasons(self, people):
        """Adults: first season already drawn; re-derive DOB so age at first season is 18-55."""
        alo, ahi = self.pop["adult_age_range"]
        for p in people:
            if p["is_minor"]:
                continue
            age = self.rng.randint(alo, ahi)
            p["dob"] = self._dob(p["first_season"] - age)

    def _designate_movers(self, people):
        pool = [p for p in people
                if p["home_country"] in ("US", "CA") and not p["twin_group_id"]
                and p["first_season"] in self.years[:-1]
                and (not p["is_minor"] or self.years[-1] - p["dob"].year <= self.pop["youth_age_range"][1])]
        n_usca = sum(1 for p in people if p["home_country"] in ("US", "CA"))
        want = round(n_usca * self.pop["cross_border_share_of_us_ca"])
        for p in self.rng.sample(pool, min(want, len(pool))):
            other = "CA" if p["home_country"] == "US" else "US"
            fr = other == "CA" and p["language"] == "fr"
            p["switch_season"] = self.rng.randint(p["first_season"] + 1, self.years[-1])
            region, alt_postal, alt_market = self._place(other, fr, by_year=p["switch_season"])      # the market they move to must have launched by then
            p["is_cross_border"] = True
            p["alt_country"], p["alt_region"] = other, region
            p["alt_postal"], p["alt_market_id"] = alt_postal, alt_market["market_id"]       # their registrations in the new country carry THIS postal code, inside that market
            # some movers register in BOTH countries in the year they move (US spring, then a Canadian club season,
            # or a Canadian season, then US fall): the same person in two countries in one year
            if self.rng.random() < self.pop["cross_border_dual_year_share"]:
                p["dual_country_year"] = p["switch_season"]

    def _flag_multi_league(self, people):
        us_youth = [p for p in people if p["segment"] == "US_YOUTH"]
        k = round(len(us_youth) * self.part["us_two_leagues_same_season_share"])
        eligible = [p for p in us_youth if not p["twin_group_id"]]   # twins always register together
        for p in self.rng.sample(eligible, k):
            p["is_multi_league"] = True

    # ---------- participation ----------
    def _churn(self, age: int) -> float:
        for band in self.part["churn_by_age"]:
            if band["min_age"] <= age <= band["max_age"]:
                return band["p"]
        return 0.0

    def _plan_person(self, p):
        """-> (active years, planned registrations) for one person."""
        r = self.rng
        ymax = self.pop["youth_age_range"][1]
        by = p["dob"].year
        active = []
        for y in self.years:
            if y < p["first_season"]:
                continue
            if y > p["first_season"] and not p["is_cross_border"]:
                if p["is_minor"] and y - by > ymax:
                    break
                if r.random() < self._churn(y - by):
                    break
            active.append(y)
        mine = []
        for y in active:
            moved = p["is_cross_border"] and y >= p["switch_season"]
            dual = p["dual_country_year"] == y
            # (country, region, only-these-US-terms) for each country played in this year
            places = ([(p["alt_country"], p["alt_region"], "FALL" if dual else None)] if moved
                      else [(p["home_country"], p["home_region"], None)])
            if dual:  # the old country as well, restricted to the part of the year before the move
                places.insert(0, (p["home_country"], p["home_region"], "SPRING"))
            for country, region, only_term in places:
                if country == "US":
                    if only_term:
                        terms = [only_term]
                    elif r.random() < self.part["us_both_terms_given_active"]:
                        terms = ["SPRING", "FALL"]
                    else:
                        terms = [r.choice(["SPRING", "FALL"])]
                else:
                    terms = ["ANNUAL"]
                for t in terms:
                    mine.append({"source_system": SOURCE_BY_COUNTRY.get(country, "INTL_FED"),
                                 "country_code": country, "region_code": region,
                                 "season_year": y, "season_term": t, "league_slot": 1})
        return active, mine

    def build_participations(self, people):
        r = self.rng
        leaders: dict[str, str] = {}      # twin group -> lead person id (lowest id)
        for p in people:
            if p["twin_group_id"]:
                leaders.setdefault(p["twin_group_id"], p["true_person_id"])
        is_follower = lambda p: bool(p["twin_group_id"]) and leaders[p["twin_group_id"]] != p["true_person_id"]  # noqa: E731
        planned: dict[str, tuple] = {}
        for p in [q for q in people if not is_follower(q)] + [q for q in people if is_follower(q)]:
            if is_follower(p):                       # twins share seasons, terms and country
                active, mine = planned[leaders[p["twin_group_id"]]]
                mine = [dict(m) for m in mine]
            else:
                active, mine = self._plan_person(p)
                if p["is_multi_league"]:
                    base = r.choice([m for m in mine if m["source_system"] == "US_LEAGUE"])
                    mine.append({**base, "league_slot": 2})
            planned[p["true_person_id"]] = (active, mine)
            p["last_season"] = active[-1]
        self._assign_name_changes(people, planned)
        rows = []
        for p in people:
            rows.extend({"true_person_id": p["true_person_id"], **m} for m in planned[p["true_person_id"]][1])
        return rows

    def _assign_name_changes(self, people, planned):
        """A few adult women in INTL appear under a different family name in a later season.
        The federation also issues a new Player ID, so no source id links the two (a known-hard case)."""
        cfg = self.pop.get("name_change", {})
        women = [p for p in people if p["segment"] == "INTL" and not p["is_minor"] and p["sex"] == "F"]
        eligible = [p for p in women if len(planned[p["true_person_id"]][0]) >= 2]
        want = max(cfg.get("min_count", 0), round(cfg.get("rate", 0) * len(women)))
        for p in self.rng.sample(eligible, min(want, len(eligible))):
            loc = self.pop["locales"][p["home_country"]]
            new = self.names.family(loc)
            p["name_change_season"] = planned[p["true_person_id"]][0][1]
            p["later_family_name"] = f"{p['family_name']}-{new}" if self.rng.random() < 0.5 else new


def _assign_ids(people: list[dict], rng: random.Random):
    """Shuffle, then number: ids and household ids must not leak segment or order."""
    rng.shuffle(people)
    hh_ids: dict[int, str] = {}
    for i, p in enumerate(people, start=1):
        p["true_person_id"] = f"P-{i:06d}"
        key = p.pop("_hh")
        if key is not None:
            if key not in hh_ids:
                hh_ids[key] = f"H-{len(hh_ids) + 1:05d}"
            p["household_id"] = hh_ids[key]


def build_population(cfg: dict | None = None):
    """-> (registry rows, participation rows), both lists of dicts, fully deterministic."""
    cfg = cfg or load_config()
    b = _Builder(cfg)
    people = b.build_people()
    _assign_ids(people, b.rng)
    people.sort(key=lambda p: p["true_person_id"])
    parts = b.build_participations(people)
    return people, parts


def write_ground_truth(people, parts, out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist([{k: p[k] for k in REGISTRY_FIELDS} for p in people]),
                   out / "person_registry.parquet")
    pq.write_table(pa.Table.from_pylist([{k: r[k] for k in PARTICIPATION_FIELDS} for r in parts]),
                   out / "participation_plan.parquet")
