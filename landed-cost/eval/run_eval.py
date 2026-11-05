"""HS 추천 평가: 정답이 후보 3개 안에 드는 비율과 범위 밖 차단 비율.

    python -m eval.run_eval            # 규칙 기반
    OPENAI_API_KEY=sk-... python -m eval.run_eval --ai   # AI 기반
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from hs.recommend import recommend, recommend_rules

SET = json.loads((Path(__file__).parent / "hs_eval_set.json").read_text(encoding="utf-8"))


def run(use_ai: bool) -> dict:
    key = os.environ.get("OPENAI_API_KEY") if use_ai else None
    if use_ai and not key:
        raise SystemExit("--ai를 쓰려면 OPENAI_API_KEY 환경 변수가 필요합니다.")
    fn = (lambda t: recommend(t, key)) if use_ai else recommend_rules
    top1 = top3 = 0
    misses = []
    for case in SET["in_scope"]:
        rec = fn(case["text"])
        codes = [c.hs6 for c in rec.candidates]
        top1 += bool(codes) and codes[0] == case["answer"]
        if case["answer"] in codes:
            top3 += 1
        else:
            misses.append({"text": case["text"], "answer": case["answer"], "got": codes, "message": rec.message})
    blocked = sum(not fn(t).in_scope for t in SET["out_of_scope"])
    n, m = len(SET["in_scope"]), len(SET["out_of_scope"])
    return {"method": "ai" if use_ai else "rules", "top1": f"{top1}/{n}", "top3": f"{top3}/{n}",
            "blocked": f"{blocked}/{m}", "misses": misses}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai", action="store_true")
    print(json.dumps(run(parser.parse_args().ai), ensure_ascii=False, indent=2))
