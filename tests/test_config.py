from config import load_config


def test_load_real_config():
    cfg = load_config("config.yaml")
    assert cfg.ollama.model == "qwen3:14b"
    assert cfg.scoring.score_threshold == 65
    assert cfg.rates["USD"] > 1
    assert cfg.sources["hh"] is True
    assert "python" in cfg.search.keywords
    assert cfg.telethon.channels == []


def test_new_keys_loaded():
    cfg = load_config("config.yaml")
    assert cfg.search.min_freelance_usd == 50
    assert "B1" in cfg.candidate_notes
    assert cfg.rates["GBP"] > cfg.rates["USD"]
    for name in ("freelancer", "pph", "remotive", "jobicy"):
        assert cfg.sources[name] is True
