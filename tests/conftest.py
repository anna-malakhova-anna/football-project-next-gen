"""Generator tests would otherwise write the whole 15,000-person dataset, with its million-line fan stream, in almost every test module. Tests get `load_config()`
returning the real config with the population and the fan stream shrunk: the structure, defects and truth files are the same, only the sizes are smaller.
tests/test_fan.py asks for `population.load_config_full()` and sets its own, larger size (it needs enough households to see the fan mechanics)."""
from generator import population

population.load_config_full = population.load_config


def _small(*args, **kwargs):
    cfg = population.load_config_full(*args, **kwargs)
    cfg["population"]["total_people"] = 4000
    cfg["sources"]["fan"]["base_events_per_month"] = 0.3
    return cfg


population.load_config = _small
