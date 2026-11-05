from decimal import Decimal as D

from calc.data import registered_rates
from calc.landed import money
from calc.quote import build_quotes
from report.pdf import build_pdf


def quotes(**kw):
    base = dict(keys=["eu:DE", "jp", "us", "uae"], hs6="330499", unit_price="8", quantity=1000, currency="USD",
                freight=500, insurance=50, rates=registered_rates())
    return build_quotes(**{**base, **kw})


def test_quotes_sorted_by_unit_cost_and_converted():
    qs = quotes()
    assert all(q.ok for q in qs)
    costs = [q.per_unit_krw for q in qs]
    assert costs == sorted(costs)
    jp = next(q for q in qs if q.dest.key == "jp")
    # FOB 8,000달러 → 엔화: 8,000 × 1,335.5 ÷ 8.952 = 1,193,476.32엔
    assert money(jp.result.amount("fob")) == D("1193476.32")


def test_fta_not_met_blocks_until_manual_rate():
    qs = quotes(fta_ok=False)
    uae = next(q for q in qs if q.dest.key == "uae")
    assert not uae.ok and "원산지" in uae.problems[0]
    assert qs[-1].dest.key in ("uae", "eu:DE", "jp")  # 계산 못 한 목적지는 뒤로
    qs2 = quotes(fta_ok=False, manual_rates={"uae": "5", "eu:DE": "0", "jp": "0"})
    assert all(q.ok for q in qs2)


def test_missing_currency_falls_back_to_usd():
    q = quotes(keys=["asean:PH"])[0]
    assert q.currency == "USD" and q.ok


def test_pdf_builds():
    qs = [q for q in quotes() if q.ok]
    best = qs[0]
    pdf = build_pdf(product="선크림 50ml", hs6="330499", hs_name="기초 화장품", quantity=1000, input_currency="USD",
                    rows=[{"name": q.dest.name, "currency": q.currency, "duty_rate": f"{q.duty_rate}%",
                           "landed_local": q.result.landed, "landed_krw": q.landed_krw, "per_unit_krw": q.per_unit_krw,
                           "flag": not q.dest.verified} for q in qs],
                    detail={"name": best.dest.name, "currency": best.currency,
                            "lines": [(l.label, l.amount, l.note) for l in best.result.lines],
                            "landed_local": best.result.landed, "landed_krw": best.landed_krw},
                    rates_note="등록 환율 2026-09-27", caveats=["테스트"])
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000
