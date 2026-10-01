import argparse
import asyncio
from pathlib import Path

import yaml

EVAL_PATH = Path("tests/scorer_eval.yaml")
THRESHOLDS = (50, 60, 65, 70, 80)


def accuracy(pairs: list[tuple[int | None, bool]], threshold: int) -> float:
    if not pairs:
        return 0.0
    hits = sum(((s is not None and s >= threshold) == fit) for s, fit in pairs)
    return hits / len(pairs)


def export() -> None:
    from config import load_config
    from storage import Storage

    st = Storage(load_config("config.yaml").db_path)
    rows = st.db.execute("SELECT * FROM vacancies WHERE status!='filtered' ORDER BY id DESC LIMIT 20")
    items = [{"id": r["id"], "source": r["source"], "title": r["title"], "company": r["company"],
              "url": r["url"], "fit": None} for r in rows]
    EVAL_PATH.write_text(yaml.safe_dump(items, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"written {len(items)} items to {EVAL_PATH}; set fit: true/false by hand")


async def run(model: str | None) -> None:
    from config import load_config
    from scorer import Scorer
    from storage import Storage

    cfg = load_config("config.yaml")
    st = Storage(cfg.db_path)
    scorer = Scorer(cfg.ollama.url, model or cfg.ollama.model, cfg.ollama.timeout_s,
                    Path(cfg.resume_path).read_text(encoding="utf-8"),
                    notes=cfg.candidate_notes)
    items = [x for x in yaml.safe_load(EVAL_PATH.read_text(encoding="utf-8")) if x["fit"] is not None]
    pairs = []
    for x in items:
        r = await scorer.score(Storage.row_to_vacancy(st.get(x["id"])))
        pairs.append((r.score, x["fit"]))
        print(f"{str(r.score):>4}  fit={x['fit']!s:5}  {x['title'][:70]}")
    for t in THRESHOLDS:
        print(f"threshold {t}: accuracy {accuracy(pairs, t):.0%}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["export", "run"])
    p.add_argument("--model")
    a = p.parse_args()
    export() if a.cmd == "export" else asyncio.run(run(a.model))
