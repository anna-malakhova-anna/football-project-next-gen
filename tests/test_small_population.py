"""The tests' small population is an explicit switch on load_config (FLAG_SMALL_POPULATION), not a patch applied at import."""
import yaml

from generator import population


def _real():
    with open("config/generation.yaml") as f:
        return yaml.safe_load(f)


def test_the_test_run_is_small_by_default():
    cfg = population.load_config()
    assert cfg["population"]["total_people"] == population.SMALL_RUN["total_people"]
    assert cfg["sources"]["fan"]["base_events_per_month"] == population.SMALL_RUN["fan_base_events_per_month"]


def test_small_false_returns_the_real_configuration():
    assert population.load_config(small=False) == _real()


def test_without_the_variable_the_configuration_is_unchanged(monkeypatch):
    monkeypatch.delenv(population.SMALL_POPULATION_ENV)
    assert population.load_config() == _real()
    assert population.load_config(small=True)["population"]["total_people"] == population.SMALL_RUN["total_people"]


def test_only_the_three_sizes_differ_in_the_small_run():
    small, real = population.load_config(), _real()
    small["population"]["total_people"] = real["population"]["total_people"]
    small["sources"]["fan"]["base_events_per_month"] = real["sources"]["fan"]["base_events_per_month"]
    small["sources"]["fan"]["account"]["stock_penetration"] = real["sources"]["fan"]["account"]["stock_penetration"]
    assert small == real
