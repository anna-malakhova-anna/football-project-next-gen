"""Organization-level data-quality profiles and structured (not uniform) defect placement. SYNTHETIC data.

Real quality problems are structured: a few organizations produce most of the defects, and some fields go missing for reasons that depend on who is registering.
This module gives every organization a latent profile, and places defects at EXACT counts (round(rate * rows), as everywhere in the generator) but with probability weights,
so overall configured rates are unchanged while the defects concentrate where the profile and the missingness mechanism say they should.

  assign_profiles   exact shares of DISCIPLINED / TYPICAL / STRUGGLING / MANUAL, ordered by a risk score: small organizations and risky regions skew to the bad profiles
  pick_weighted     exact-count weighted sampling without replacement (Efraimidis-Spirakis keys)
Everything is seeded by the caller's random.Random; truth about profiles and mechanisms is written to data/ground_truth only.
"""
from __future__ import annotations

import math
import random

PROFILES = ["DISCIPLINED", "TYPICAL", "STRUGGLING", "MANUAL"]


def assign_profiles(rng: random.Random, orgs: list[dict], cfg: dict) -> dict[str, str]:
    """orgs: [{org_id, region, n_records}] -> {org_id: profile}. Shares are exact (rounded, remainder to TYPICAL); order is by risk = small size + risky region + noise."""
    q = cfg["org_quality"]
    mix = q["profile_mix"]
    risky = set(q["risky_regions"])
    sizes = [max(o["n_records"], 1) for o in orgs]
    lo, hi = math.log(min(sizes)), math.log(max(sizes))
    scored = []
    for o, n in zip(orgs, sizes):
        small = 1 - (math.log(n) - lo) / (hi - lo) if hi > lo else 0.5          # 1 = smallest
        score = q["size_weight"] * small + q["region_weight"] * (o["region"] in risky) + q["noise"] * rng.random()
        scored.append((score, o["org_id"]))
    scored.sort(reverse=True)                                                    # riskiest first
    n = len(scored)
    k_manual = max(round(mix["MANUAL"] * n), 1 if mix["MANUAL"] > 0 and n >= 10 else 0)
    k_struggling = round(mix["STRUGGLING"] * n)
    k_disciplined = round(mix["DISCIPLINED"] * n)
    out = {}
    for i, (_, oid) in enumerate(scored):
        if i < k_manual:
            out[oid] = "MANUAL"
        elif i < k_manual + k_struggling:
            out[oid] = "STRUGGLING"
        elif i >= n - k_disciplined:
            out[oid] = "DISCIPLINED"
        else:
            out[oid] = "TYPICAL"
    return out


def pick_weighted(rng: random.Random, eligible: list[int], weights: dict[int, float] | list[float], rate: float, total: int) -> list[int]:
    """Choose round(rate * total) indices from `eligible` without replacement, with probability proportional to weight (all of them if too few).
    Weighted sampling by keys u**(1/w); a zero weight is never chosen unless there is nothing else."""
    k = min(round(rate * total), len(eligible))
    if k <= 0:
        return []
    keyed = []
    for i in eligible:
        w = weights[i]
        keyed.append((rng.random() ** (1.0 / w) if w > 0 else -1.0, i))
    keyed.sort(reverse=True)
    return [i for _, i in keyed[:k]]


def multiplier(cfg: dict, profile: str) -> float:
    return float(cfg["org_quality"]["defect_multiplier"][profile])


def assign_consent_versions(rng: random.Random, org_ids: list[str], profiles: dict[str, str], cfg: dict) -> dict[str, str | None]:
    """Each org's form uses one consent wording (by the configured shares); MANUAL orgs have none (the consent fields are missing entirely, so the wording is unknown)."""
    versions = cfg["org_quality"]["consent_text_versions"]
    names = list(versions)
    shares = [versions[v]["share"] for v in names]
    out: dict[str, str | None] = {}
    for oid in org_ids:
        out[oid] = None if profiles[oid] == "MANUAL" else rng.choices(names, weights=shares)[0]
    return out


def channel_for(rng: random.Random, profile: str) -> str:
    """The registration channel the program KNOWS an org uses (a proxy for quality, not the profile itself): preferred platform, another platform, or spreadsheet."""
    probs = {"DISCIPLINED": [0.85, 0.15, 0.0], "TYPICAL": [0.55, 0.40, 0.05], "STRUGGLING": [0.15, 0.55, 0.30], "MANUAL": [0.0, 0.15, 0.85]}[profile]
    return rng.choices(["PREFERRED_PLATFORM", "OTHER_PLATFORM", "SPREADSHEET"], weights=probs)[0]


def pick_unreporting(rng: random.Random, existing: dict[int, list[str]], cfg: dict) -> dict[int, set[str]]:
    """For each season, the known organizations that send no file. `existing[year]` lists the organizations that exist that season (an organization is known only from its first season on);
    the share that goes dark is drawn from the configured range (15 to 25 percent) of THEM. An org can be dark one season and report the next."""
    lo, hi = cfg["org_quality"]["unreporting"]["share_range"]
    out = {}
    for y in sorted(existing):
        orgs = sorted(existing[y])
        out[y] = set(rng.sample(orgs, round(rng.uniform(lo, hi) * len(orgs)))) if orgs else set()
    return out


def fix_list_adopters(cfg: dict, profiles: dict[str, str]) -> set[str]:
    """Spec 3.5, OFF by default. The STRUGGLING organizations that "received" a fix list and act on it: an exact share of them, chosen with a stream of their own (so switching the scenario
    on or off never shifts any other draw). Empty when the scenario is disabled. Used only by the simulated feedback-loop demo."""
    a = cfg["org_quality"].get("fix_list_adoption") or {}
    if not a.get("enabled"):
        return set()
    struggling = sorted(o for o, p in profiles.items() if p == "STRUGGLING")
    k = round(float(a["share_of_struggling_orgs"]) * len(struggling))
    rng = random.Random(cfg["seed"] + 53)
    return set(rng.sample(struggling, k)) if k else set()


def profile_in_season(cfg: dict, org: str, year: int, profile: str, adopters: set[str]) -> str:
    """The profile an organization's file shows in a season: an adopter improves in the final season only."""
    a = cfg["org_quality"].get("fix_list_adoption") or {}
    if org in adopters and year == max(cfg["seasons"]["years"]):
        return a["final_season_improves_to"]
    return profile
