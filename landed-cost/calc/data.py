"""등록 데이터(관세율·과세 규칙·환율)를 읽고 목적지별로 정리합니다."""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from .landed import TaxRule, dec

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=None)
def _load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Destination:
    key: str           # "eu:DE", "jp", "asean:VN"
    region: str
    member: str | None
    name: str
    currency: str
    rule: TaxRule
    verified: bool
    notes: tuple[str, ...]
    source_url: str | None


def destinations() -> list[Destination]:
    rules = _load("tax_rules.json")["regions"]
    out: list[Destination] = []
    for region, r in rules.items():
        if "members" in r:
            for code, m in r["members"].items():
                out.append(_dest(region, code, f"{r['name']} · {m['name']}", {**r, **m}))
        else:
            out.append(_dest(region, None, r["name"], r))
    return out


def _dest(region, member, name, r) -> Destination:
    vat = r.get("vat")
    ct = r.get("consumption_tax")
    rule = TaxRule(
        basis=r["basis"],
        vat=None if vat is None else Decimal(str(vat)),
        vat_label=r.get("vat_label", "부가세"),
        mpf=r.get("mpf"),
        hmf=r.get("hmf"),
        consumption_tax=Decimal(str(ct["rate"])) if ct else None,
    )
    notes = tuple(n for n in (r.get("basis_note"), r.get("vat_note"), r.get("currency_note"),
                              ct.get("applies_note") if ct else None) if n)
    return Destination(
        key=f"{region}:{member}" if member else region, region=region, member=member, name=name,
        currency=r["currency"], rule=rule, verified=bool(r.get("verified")), notes=notes,
        source_url=r.get("source_url") or (r.get("mpf") or {}).get("source_url"),
    )


def destination(key: str) -> Destination:
    for d in destinations():
        if d.key == key:
            return d
    raise KeyError(key)


def tariff_row(dest: Destination, hs6: str) -> dict | None:
    """목적지와 HS 6자리로 등록 관세 행을 찾습니다. EU는 회원국 공통 세율을 씁니다."""
    for row in _load("tariffs.json")["rows"]:
        if row["region"] != dest.region or row["hs6"] != hs6:
            continue
        if dest.region == "asean" and row["member"] != dest.member:
            continue
        return row
    return None


# --- 환율 -----------------------------------------------------------------

@dataclass(frozen=True)
class Rates:
    as_of: str
    source: str
    table: dict  # 통화 → (원화 환율, 고시 단위)

    def has(self, currency: str) -> bool:
        return currency == "KRW" or currency in self.table

    def to_krw(self, currency: str) -> Decimal:
        """1 통화 단위가 몇 원인지."""
        if currency == "KRW":
            return Decimal(1)
        krw, unit = self.table[currency]
        return krw / unit

    def convert(self, amount, source: str, target: str) -> Decimal:
        """BEAUPORT 환율 계산기와 같은 산식: 금액 × (기준 환율 ÷ 고시 단위) ÷ (대상 환율 ÷ 고시 단위)."""
        a = dec(amount, "금액")
        if source == target:
            return a
        return a * self.to_krw(source) / self.to_krw(target)


def registered_rates() -> Rates:
    raw = _load("exchange_rates.json")
    table = {r["currency"]: (Decimal(str(r["krw_rate"])), Decimal(str(r["unit"]))) for r in raw["rates"]}
    if "CNH" in table:
        table.setdefault("CNY", table["CNH"])
    return Rates(as_of=raw["as_of"], source=raw["source"], table=table)


def hs_catalog() -> list[dict]:
    return _load("hs_catalog.json")["items"]


def out_of_scope_keywords() -> list[str]:
    return _load("hs_catalog.json")["out_of_scope_keywords"]
