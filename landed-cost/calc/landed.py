"""착지가 계산. AI를 쓰지 않고 규칙과 공식만으로 계산합니다.

모든 금액은 목적국 통화 하나로 맞춘 뒤 Decimal로 계산하고,
반올림은 화면이나 보고서에 보여 줄 때만 합니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

D = Decimal
HUNDRED = D("100")


def dec(value, name: str) -> Decimal:
    try:
        number = D(str(value))
    except Exception:
        raise ValueError(f"{name}은(는) 숫자로 입력해 주세요.") from None
    if not number.is_finite():
        raise ValueError(f"{name}은(는) 숫자로 입력해 주세요.")
    return number


def money(value: Decimal, places: str = "0.01") -> Decimal:
    """보여 줄 때만 쓰는 반올림 (사사오입)."""
    return value.quantize(D(places), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TaxRule:
    """목적지 한 곳의 과세 규칙."""
    basis: str                      # "CIF" 또는 "FOB"
    vat: Decimal | None             # 부가세율(%), 모르면 None
    vat_label: str = "부가세"
    mpf: dict | None = None         # 미국 통관 수수료 {rate, min, max} (USD)
    hmf: dict | None = None         # 미국 항만 유지비 {rate, applies}
    consumption_tax: Decimal | None = None  # 중국 고급 화장품 소비세(%)


@dataclass
class Line:
    key: str
    label: str
    amount: Decimal
    note: str = ""


@dataclass
class Result:
    lines: list[Line] = field(default_factory=list)
    customs_value: Decimal = D(0)
    duty: Decimal = D(0)
    taxes: Decimal = D(0)
    landed: Decimal = D(0)
    per_unit: Decimal = D(0)

    def amount(self, key: str) -> Decimal:
        for line in self.lines:
            if line.key == key:
                return line.amount
        return D(0)


def compute(*, fob: object, quantity: object, freight: object = 0, insurance: object = 0,
            duty_rate: object, rule: TaxRule, transport: str = "sea",
            premium_cosmetics: bool = False, include_vat: bool = True,
            vat_override: object | None = None, other_costs: object = 0) -> Result:
    """목적국 통화로 맞춘 금액을 받아 착지가를 계산합니다.

    fob: 총 FOB 금액 (단가 × 수량)
    duty_rate: 적용 관세율(%)
    include_vat: False면 부가세를 비용에서 뺍니다 (매입세액 공제를 받는 수입자).
    other_costs: 통관 대행료 등. 과세가격에는 넣지 않습니다.
    """
    fob = dec(fob, "FOB 금액")
    qty = dec(quantity, "수량")
    freight = dec(freight, "운임")
    insurance = dec(insurance, "보험료")
    rate = dec(duty_rate, "관세율")
    other = dec(other_costs, "기타 비용")
    if qty <= 0:
        raise ValueError("수량은 1 이상이어야 합니다.")
    if min(fob, freight, insurance, other) < 0 or rate < 0:
        raise ValueError("금액과 세율은 0 이상이어야 합니다.")
    if rule.basis not in ("CIF", "FOB"):
        raise ValueError("과세 기준은 CIF 또는 FOB여야 합니다.")
    if transport not in ("sea", "air"):
        raise ValueError("운송 방식은 sea 또는 air여야 합니다.")

    vat_rate = rule.vat if vat_override is None else dec(vat_override, "부가세율")
    if vat_rate is None and include_vat:
        raise ValueError("이 목적지의 부가세율이 등록되지 않았습니다. 직접 입력해 주세요.")

    result = Result()
    add = result.lines.append
    add(Line("fob", "FOB 금액", fob))
    add(Line("freight", "운임", freight))
    add(Line("insurance", "보험료", insurance))

    cv = fob + freight + insurance if rule.basis == "CIF" else fob
    result.customs_value = cv
    duty = cv * rate / HUNDRED
    result.duty = duty
    add(Line("duty", "관세", duty, f"과세가격({rule.basis}) × {rate}%"))

    taxes = D(0)
    if rule.mpf:
        raw = fob * D(str(rule.mpf["rate"])) / HUNDRED
        mpf = min(max(raw, D(str(rule.mpf["min"]))), D(str(rule.mpf["max"])))
        add(Line("mpf", "통관 수수료(MPF)", mpf, f"{rule.mpf['rate']}%, 최소 {rule.mpf['min']} · 최대 {rule.mpf['max']}"))
        taxes += mpf
    if rule.hmf and transport == rule.hmf.get("applies", "sea"):
        hmf = fob * D(str(rule.hmf["rate"])) / HUNDRED
        add(Line("hmf", "항만 유지비(HMF)", hmf, f"해상 운송 {rule.hmf['rate']}%"))
        taxes += hmf

    vat_base = cv + duty
    if premium_cosmetics and rule.consumption_tax:
        ct_rate = rule.consumption_tax / HUNDRED
        ct = vat_base / (1 - ct_rate) * ct_rate
        add(Line("consumption_tax", "소비세", ct, f"(과세가격 + 관세) ÷ (1 − {rule.consumption_tax}%) × {rule.consumption_tax}%"))
        taxes += ct
        vat_base += ct

    if include_vat and vat_rate:
        vat = vat_base * vat_rate / HUNDRED
        add(Line("vat", rule.vat_label, vat, f"(과세가격 + 관세{' + 소비세' if premium_cosmetics and rule.consumption_tax else ''}) × {vat_rate}%"))
        taxes += vat

    if other:
        add(Line("other", "기타 비용", other, "과세가격에 넣지 않음"))

    result.taxes = taxes
    result.landed = fob + freight + insurance + duty + taxes + other
    result.per_unit = result.landed / qty
    return result


def select_rate(row: dict | None, fta_ok: bool, manual_rate: object | None = None) -> tuple[Decimal | None, str]:
    """등록된 관세 행과 FTA 충족 여부로 적용 세율을 고릅니다.

    돌려주는 값: (세율 또는 None, 설명). None이면 사용자가 세율을 직접 넣어야 합니다.
    """
    if manual_rate not in (None, ""):
        return dec(manual_rate, "관세율"), "직접 입력한 세율"
    if row is None:
        return None, "이 품목의 등록 관세율이 없습니다. 세율을 직접 입력해 주세요."
    rate = dec(row["rate"], "관세율")
    basis = row.get("basis")
    if basis == "FTA" and not fta_ok:
        return None, (f"등록된 세율은 {row.get('agreement') or 'FTA'} 협정 세율입니다. "
                      "원산지 요건을 충족하지 못하면 일반 세율을 직접 입력해 주세요.")
    label = {"FTA": "FTA 협정 세율", "MFN": "일반(기본) 세율", "ADD": "추가 관세 포함 세율"}.get(basis, "등록 세율")
    return rate, f"{label} · {row.get('agreement', '')}".strip(" ·")
