"""화면과 리포트가 함께 쓰는 견적 조립: 통화 변환 → 세율 선택 → 계산."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .data import Destination, Rates, destination, tariff_row
from .landed import Result, compute, dec, select_rate


@dataclass
class Quote:
    dest: Destination
    currency: str                     # 계산에 쓴 현지 통화
    duty_rate: Decimal | None
    rate_note: str
    tariff: dict | None
    result: Result | None = None
    landed_krw: Decimal | None = None
    per_unit_krw: Decimal | None = None
    problems: list[str] = field(default_factory=list)   # 계산을 막은 이유
    cautions: list[str] = field(default_factory=list)   # 계산은 했지만 확인할 점

    @property
    def ok(self) -> bool:
        return self.result is not None


def build_quotes(*, keys: list[str], hs6: str, unit_price, quantity, currency: str, freight=0, insurance=0,
                 rates: Rates, fta_ok: bool = True, transport: str = "sea", premium_cosmetics: bool = False,
                 include_vat: bool = True, manual_rates: dict | None = None, vat_overrides: dict | None = None,
                 other_costs=0) -> list[Quote]:
    manual_rates = manual_rates or {}
    vat_overrides = vat_overrides or {}
    qty = dec(quantity, "수량")
    fob_in = dec(unit_price, "단가") * qty
    out: list[Quote] = []
    for key in dict.fromkeys(keys):  # 같은 목적지를 두 번 고르면 한 번만 계산
        d = destination(key)
        cur = d.currency if rates.has(d.currency) else "USD"
        row = tariff_row(d, hs6)
        rate, note = select_rate(row, fta_ok, manual_rates.get(key))
        q = Quote(dest=d, currency=cur, duty_rate=rate, rate_note=note, tariff=row)
        if cur != d.currency:
            q.cautions.append(f"{d.currency} 환율이 없어 달러로 계산했습니다.")
        if not d.verified:
            q.cautions.append("이 목적지의 세금 정보는 공식 출처 확인이 필요합니다.")
        q.cautions += list(d.notes)
        if row and row.get("conditions") and row.get("basis") == "FTA" and fta_ok:
            q.cautions.append(f"FTA 세율 조건: {row['conditions']}")
        if rate is None:
            q.problems.append(note)
            out.append(q)
            continue
        conv = lambda v: rates.convert(v, currency, cur)
        try:
            q.result = compute(fob=conv(fob_in), quantity=qty, freight=conv(freight), insurance=conv(insurance),
                               duty_rate=rate, rule=d.rule, transport=transport, premium_cosmetics=premium_cosmetics,
                               include_vat=include_vat, vat_override=vat_overrides.get(key), other_costs=conv(other_costs))
        except ValueError as error:
            q.problems.append(str(error))
            out.append(q)
            continue
        q.landed_krw = rates.convert(q.result.landed, cur, "KRW")
        q.per_unit_krw = q.landed_krw / qty
        out.append(q)
    # 계산된 것은 개당 착지가가 낮은 순, 계산 못 한 것은 뒤로
    out.sort(key=lambda q: (not q.ok, q.per_unit_krw or 0))
    return out
