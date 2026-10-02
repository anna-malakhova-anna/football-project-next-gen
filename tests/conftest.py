"""The fan event stream (Source D) is over a million lines at full size, and almost every generator test writes the whole dataset. Tests get
`load_config()` returning the real config with the fan stream shrunk: the structure, defects and truth files are the same,
only the number of non-participant households and events per month is smaller. tests/test_fan.py uses the real config
(`population.load_config_full`)."""
from generator import population

population.load_config_full = population.load_config


def _small(*args, **kwargs):
    cfg = population.load_config_full(*args, **kwargs)
    cfg["sources"]["fan"].update(non_participant_household_multiple=0.2, base_events_per_month=0.3)
    return cfg


population.load_config = _small
