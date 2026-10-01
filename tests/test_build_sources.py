from config import load_config
from sources import build_sources


def test_build_sources_respects_flags():
    cfg = load_config("config.yaml")
    names = [s.name for s in build_sources(cfg)]
    assert names == ["hh", "habr_career", "getmatch", "remoteok", "wwr", "himalayas", "kwork", "fl",
                     "freelancer", "pph", "remotive", "jobicy"]
    cfg.sources["kwork"] = False
    assert "kwork" not in [s.name for s in build_sources(cfg)]
