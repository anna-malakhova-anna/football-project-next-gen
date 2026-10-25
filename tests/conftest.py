"""Generator tests would otherwise write the whole 15,000-person dataset, with its million-line fan stream, in almost every test module.
The tests run with FLAG_SMALL_POPULATION=1, which `generator.population.load_config()` reads: the real configuration with the population and the
fan stream shrunk. The structure, defects and truth files are the same, only the sizes are smaller. tests/test_fan.py calls
`load_config(small=False)` and sets its own, larger size (it needs enough households to see the fan mechanics)."""
import os

from generator.population import SMALL_POPULATION_ENV


def pytest_configure(config):
    config._flag_small_before = os.environ.get(SMALL_POPULATION_ENV)
    os.environ[SMALL_POPULATION_ENV] = "1"


def pytest_unconfigure(config):
    before = getattr(config, "_flag_small_before", None)
    if before is None:
        os.environ.pop(SMALL_POPULATION_ENV, None)
    else:
        os.environ[SMALL_POPULATION_ENV] = before
