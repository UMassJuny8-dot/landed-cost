"""착지가 계산 테스트. 기대값은 모두 손으로 계산한 값입니다(주석에 계산 과정)."""
from decimal import Decimal as D

import pytest

from calc.data import destination, registered_rates, tariff_row
from calc.landed import TaxRule, compute, money, select_rate

CIF = dict(fob=10000, freight=500, insurance=100, quantity=1000)  # 과세가격 CIF = 10,600


def rule(key):
    return destination(key).rule


def total(result):
    return money(result.landed)


# ---- 1~3 EU ---------------------------------------------------------------

def test_01_eu_germany_cif_vat19():
    # 10,600 × 0% = 0 / VAT (10,600) × 19% = 2,014 / 합계 12,614
    r = compute(**CIF, duty_rate=0, rule=rule("eu:DE"))
    assert money(r.amount("vat")) == D("2014.00")
    assert total(r) == D("12614.00")


def test_02_eu_france_vat20():
    # VAT 10,600 × 20% = 2,120 / 합계 12,720
    assert total(compute(**CIF, duty_rate=0, rule=rule("eu:FR"))) == D("12720.00")


def test_03_vat_excluded_for_reclaiming_importer():
    # 매입세액 공제를 받는 수입자: 부가세를 비용에서 뺌 → 10,600
    assert total(compute(**CIF, duty_rate=0, rule=rule("eu:DE"), include_vat=False)) == D("10600.00")


# ---- 4 일본 ---------------------------------------------------------------

def test_04_japan_cif_consumption_tax10():
    # CIF 1,060,000 / 소비세 106,000 / 합계 1,166,000
    r = compute(fob=1_000_000, freight=50_000, insurance=10_000, quantity=1, duty_rate=0, rule=rule("jp"))
    assert total(r) == D("1166000.00")


# ---- 5~8 미국 (FOB 기준, MPF·HMF) -------------------------------------------

def test_05_us_fob_basis_with_mpf_and_hmf():
    # 과세가격 = FOB 10,000 (운임·보험료 제외) / 관세 12.5% = 1,250
    # MPF 10,000 × 0.3464% = 34.64 (최소 34.58보다 큼) / HMF 0.125% = 12.50
    # 합계 10,000 + 800 + 50 + 1,250 + 34.64 + 12.50 = 12,147.14
    r = compute(fob=10000, freight=800, insurance=50, quantity=100, duty_rate=12.5, rule=rule("us"))
    assert r.customs_value == D(10000)
    assert money(r.amount("mpf")) == D("34.64")
    assert money(r.amount("hmf")) == D("12.50")
    assert total(r) == D("12147.14")


def test_06_us_mpf_minimum():
    # MPF 5,000 × 0.3464% = 17.32 → 최소 34.58 / 관세 625 / HMF 6.25 → 5,665.83
    r = compute(fob=5000, quantity=10, duty_rate=12.5, rule=rule("us"))
    assert r.amount("mpf") == D("34.58")
    assert total(r) == D("5665.83")


def test_07_us_mpf_maximum_air():
    # MPF 300,000 × 0.3464% = 1,039.20 → 최대 670.86 / 항공이라 HMF 없음
    # 300,000 + 37,500 + 670.86 = 338,170.86
    r = compute(fob=300000, quantity=10, duty_rate=12.5, rule=rule("us"), transport="air")
    assert r.amount("mpf") == D("670.86")
    assert r.amount("hmf") == D(0)
    assert total(r) == D("338170.86")


def test_08_us_no_vat_line():
    r = compute(fob=10000, quantity=1, duty_rate=12.5, rule=rule("us"), transport="air")
    assert r.amount("vat") == D(0)
    assert total(r) == D("11284.64")  # 10,000 + 1,250 + 34.64


# ---- 9~10 중국 (소비세) ------------------------------------------------------

def test_09_china_general_cosmetics():
    # 관세 10,600 × 5% = 530 / 증치세 (11,130) × 13% = 1,446.90 / 합계 12,576.90
    r = compute(**CIF, duty_rate=5, rule=rule("cn"))
    assert money(r.amount("vat")) == D("1446.90")
    assert total(r) == D("12576.90")


def test_10_china_premium_consumption_tax():
    # 소비세 = 11,130 ÷ 0.85 × 0.15 = 1,964.12 / 증치세 = (11,130 + 1,964.12) × 13% = 1,702.24
    # 합계 10,600 + 530 + 1,964.12 + 1,702.24 = 14,796.35 (반올림 전 값 합산)
    r = compute(**CIF, duty_rate=5, rule=rule("cn"), premium_cosmetics=True)
    assert money(r.amount("consumption_tax")) == D("1964.12")
    assert money(r.amount("vat")) == D("1702.24")
    assert total(r) == D("14796.35")


# ---- 11~13 UAE · 러시아 ------------------------------------------------------

def test_11_uae_cepa_duty_and_vat5():
    # 관세 10,600 × 4.5% = 477 / VAT 11,077 × 5% = 553.85 / 합계 11,630.85
    assert total(compute(**CIF, duty_rate=4.5, rule=rule("uae"))) == D("11630.85")


def test_12_russia_vat22():
    # 관세 10,600 × 6.5% = 689 / VAT 11,289 × 22% = 2,483.58 / 합계 13,772.58
    assert total(compute(**CIF, duty_rate=6.5, rule=rule("eac"))) == D("13772.58")


def test_13_vat_override():
    # 베트남 8% 감면을 적용하는 경우: 관세 530 / VAT 11,130 × 8% = 890.40 → 12,020.40
    assert total(compute(**CIF, duty_rate=5, rule=rule("asean:VN"), vat_override=8)) == D("12020.40")


# ---- 14~17 ASEAN -----------------------------------------------------------

def test_14_vietnam_duty5_vat10():
    # 530 + 1,113 → 12,243
    assert total(compute(**CIF, duty_rate=5, rule=rule("asean:VN"))) == D("12243.00")


def test_15_thailand_vat7():
    assert total(compute(**CIF, duty_rate=0, rule=rule("asean:TH"))) == D("11342.00")


def test_16_singapore_gst9():
    assert total(compute(**CIF, duty_rate=0, rule=rule("asean:SG"))) == D("11554.00")


def test_17_brunei_no_vat():
    assert total(compute(**CIF, duty_rate=0, rule=rule("asean:BN"))) == D("10600.00")


# ---- 18~20 공통 -------------------------------------------------------------

def test_18_per_unit_cost():
    # 12,614 ÷ 1,000개 = 12.614
    assert compute(**CIF, duty_rate=0, rule=rule("eu:DE")).per_unit == D("12.614")


def test_19_other_costs_not_in_tax_base():
    # 기타 비용 300은 부가세 기준에 넣지 않음 → 12,614 + 300 = 12,914
    r = compute(**CIF, duty_rate=0, rule=rule("eu:DE"), other_costs=300)
    assert money(r.amount("vat")) == D("2014.00")
    assert total(r) == D("12914.00")


def test_20_invalid_inputs():
    with pytest.raises(ValueError):
        compute(fob=100, quantity=0, duty_rate=0, rule=rule("jp"))
    with pytest.raises(ValueError):
        compute(fob=-1, quantity=1, duty_rate=0, rule=rule("jp"))
    with pytest.raises(ValueError):  # 미얀마는 세율 미등록 → 직접 입력 필요
        compute(fob=100, quantity=1, duty_rate=0, rule=rule("asean:MM"))


# ---- 세율 선택·데이터·환율 -----------------------------------------------------

def test_select_rate_fta_needs_origin():
    row = tariff_row(destination("uae"), "330499")
    assert select_rate(row, fta_ok=True)[0] == D("4.5")
    rate, why = select_rate(row, fta_ok=False)
    assert rate is None and "원산지" in why
    assert select_rate(row, fta_ok=False, manual_rate="5")[0] == D(5)


def test_select_rate_mfn_and_missing():
    assert select_rate(tariff_row(destination("eac"), "330499"), fta_ok=False)[0] == D("6.5")
    assert select_rate(tariff_row(destination("eu:DE"), "330510"), fta_ok=True)[0] is None  # 샴푸는 미등록


def test_asean_rows_are_member_specific():
    assert tariff_row(destination("asean:VN"), "330410")["rate"] == 5
    assert tariff_row(destination("asean:TH"), "330410")["rate"] == 0


def test_fx_uses_notice_unit():
    rates = registered_rates()
    # 100엔 = 895.20원 → 10,000엔 = 89,520원
    assert money(rates.convert(10000, "JPY", "KRW")) == D("89520.00")
    # 1달러 = 1,335.50원 → 엔화로 1달러 = 1,335.50 ÷ 8.952 = 149.18엔
    assert money(rates.convert(1, "USD", "JPY")) == D("149.18")


def test_every_destination_has_rule_and_currency():
    from calc.data import destinations
    for d in destinations():
        assert d.rule.basis in ("CIF", "FOB")
        assert registered_rates().has(d.currency), d.key
