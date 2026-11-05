"""수출 착지가 계산기 · Streamlit 화면.

계산은 calc/, HS 추천은 hs/, PDF는 report/에 있고 이 파일은 화면만 그립니다.
실행: streamlit run app.py
"""
from __future__ import annotations

from decimal import Decimal

import pandas as pd
import streamlit as st

from calc.data import destinations, hs_catalog
from calc.fx_live import live_rates
from calc.landed import money
from calc.quote import build_quotes
from hs.recommend import recommend

st.set_page_config(page_title="수출 착지가 계산기", page_icon="📦", layout="wide")


def secret(name: str, default: str | None = None) -> str | None:
    try:
        return st.secrets.get(name, default)
    except Exception:  # secrets.toml이 없을 때
        return default


OPENAI_KEY = secret("OPENAI_API_KEY")
OPENAI_MODEL = secret("OPENAI_MODEL", "gpt-4.1-mini")
EXCHANGE_KEY = secret("EXCHANGE_API_KEY")

EXAMPLES = {
    "선크림": ("무기자차 선크림 SPF50+ PA++++ 50ml", "징크옥사이드 기반 무기자차 자외선 차단 크림, 튜브 50ml"),
    "폼클렌저": ("약산성 폼클렌저 150ml", "약산성 세안용 클렌징 폼, 튜브 150ml, 물로 헹구는 제품"),
    "립틴트": ("벨벳 립틴트 4g", "매트한 질감의 입술용 틴트, 4g"),
}
CATALOG = {i["hs6"]: i for i in hs_catalog()}
DESTS = {d.key: d for d in destinations()}


@st.cache_data(ttl=3600, show_spinner=False)
def get_rates(key: str | None):
    return live_rates(key)


def fmt(value, places=0) -> str:
    return f"{money(Decimal(value), '1' if places == 0 else '0.' + '0' * places):,}"


ss = st.session_state
ss.setdefault("product", "")
ss.setdefault("desc", "")
ss.setdefault("rec", None)

st.title("수출 착지가 계산기")
st.caption("화장품 제품 설명으로 HS 코드 후보를 찾고, 목적지별 관세·부가세·환율을 합쳐 현지 도착 원가를 계산합니다. "
           "HS 코드는 참고용 후보이며, 확정은 관세사 또는 관세청 품목분류 사전심사로 하세요.")

rates, fx_warning = get_rates(EXCHANGE_KEY)
if fx_warning:
    st.warning(fx_warning)

# ---- 1. 제품 입력 ------------------------------------------------------------
with st.container(border=True):
    st.subheader("1. 제품 입력")
    cols = st.columns(len(EXAMPLES) + 1)
    cols[0].caption("예시로 채우기")
    for col, (label, (name, desc)) in zip(cols[1:], EXAMPLES.items()):
        if col.button(label, key=f"ex-{label}", use_container_width=True):
            ss.product, ss.desc, ss.rec = name, desc, None
    st.text_input("제품명", key="product", placeholder="예: 무기자차 선크림 SPF50+ 50ml")
    st.text_area("제품 설명 (용도·제형·용량)", key="desc", height=80,
                 placeholder="예: 징크옥사이드 기반 자외선 차단 크림, 튜브 50ml")
    method = "AI(OpenAI) 추천" if OPENAI_KEY else "규칙 기반 추천 (OpenAI 키를 넣으면 AI로 추천합니다)"
    if st.button("HS 코드 후보 찾기", type="primary", disabled=not (ss.product or ss.desc)):
        with st.spinner("후보를 찾는 중…"):
            ss.rec = recommend(f"{ss.product} {ss.desc}", OPENAI_KEY, OPENAI_MODEL)
    st.caption(method)

# ---- 2. HS 코드 선택 -----------------------------------------------------------
rec = ss.rec
hs6 = None
with st.container(border=True):
    st.subheader("2. HS 코드 선택")
    if rec is None:
        st.info("제품을 입력하고 ‘HS 코드 후보 찾기’를 누르세요.")
    else:
        for w in rec.warnings:
            st.warning(w)
        options = []
        if rec.in_scope:
            st.caption(f"{'AI' if rec.method == 'ai' else '규칙 기반'} 추천 · 등록된 HS 33류·3401류 목록 안에서만 고릅니다.")
            for i, c in enumerate(rec.candidates):
                with st.container(border=True):
                    st.markdown(f"**{c.hs6[:4]}.{c.hs6[4:]} · {c.name}**  \n확신도 {c.confidence} · {c.reason}")
                options.append(c.hs6)
        else:
            st.error(rec.message)
        manual = "목록에서 직접 고르기"
        choice = st.radio("사용할 HS 코드", options + [manual], horizontal=True,
                          format_func=lambda x: x if x == manual else f"{x[:4]}.{x[4:]}")
        if choice == manual:
            hs6 = st.selectbox("HS 코드", list(CATALOG), format_func=lambda x: f"{x[:4]}.{x[4:]} {CATALOG[x]['name']}")
        else:
            hs6 = choice

# ---- 3. 수출 조건 -------------------------------------------------------------
with st.container(border=True):
    st.subheader("3. 수출 조건")
    keys = st.multiselect("목적지 (여러 곳 비교)", list(DESTS), default=["eu:DE", "jp", "us", "asean:VN"],
                          format_func=lambda k: DESTS[k].name)
    c1, c2, c3, c4 = st.columns(4)
    currency = c1.selectbox("입력 통화", ["USD", "KRW", "EUR", "JPY"])
    unit_price = c2.number_input("FOB 단가", min_value=0.0, value=8.0, step=0.5, format="%.2f")
    quantity = c3.number_input("수량(개)", min_value=1, value=1000, step=100)
    transport = c4.radio("운송", ["sea", "air"], format_func=lambda x: "해상" if x == "sea" else "항공", horizontal=True)
    c5, c6, c7 = st.columns(3)
    freight = c5.number_input("국제 운임 (총액)", min_value=0.0, value=500.0, step=50.0)
    insurance = c6.number_input("적하 보험료 (총액)", min_value=0.0, value=50.0, step=10.0)
    other = c7.number_input("기타 비용 (통관 대행료 등)", min_value=0.0, value=0.0, step=10.0)
    o1, o2, o3 = st.columns(3)
    fta_ok = o1.checkbox("FTA 원산지 요건 충족 (원산지증명서 준비)", value=True)
    include_vat = o2.checkbox("수입 부가세를 비용에 포함", value=True,
                              help="수입자가 매입세액 공제를 받으면 부가세는 비용이 아닙니다. 그럴 땐 끄세요.")
    premium = o3.checkbox("중국 고급 화장품 소비세 대상", value=False, disabled="cn" not in keys)

if not (hs6 and keys):
    st.stop()

manual_rates, vat_overrides = ss.setdefault("manual_rates", {}), ss.setdefault("vat_overrides", {})
quotes = build_quotes(keys=keys, hs6=hs6, unit_price=unit_price, quantity=quantity, currency=currency,
                      freight=freight, insurance=insurance, rates=rates, fta_ok=fta_ok, transport=transport,
                      premium_cosmetics=premium, include_vat=include_vat, manual_rates=manual_rates,
                      vat_overrides=vat_overrides, other_costs=other)

blocked = [q for q in quotes if not q.ok]
if blocked:
    with st.container(border=True):
        st.subheader("세율 직접 입력")
        st.caption("등록 데이터로 계산할 수 없는 목적지입니다. 확인한 세율을 넣으면 바로 계산합니다.")
        for q in blocked:
            st.markdown(f"**{q.dest.name}** · {' / '.join(q.problems)}")
            a, b = st.columns(2)
            if q.duty_rate is None:
                v = a.number_input("관세율(%)", min_value=0.0, step=0.5, key=f"mr-{q.dest.key}", value=None)
                if v is not None:
                    manual_rates[q.dest.key] = str(v)
            if q.dest.rule.vat is None:
                v = b.number_input("부가세율(%)", min_value=0.0, step=0.5, key=f"vr-{q.dest.key}", value=None)
                if v is not None:
                    vat_overrides[q.dest.key] = str(v)
        if st.button("입력한 세율로 다시 계산"):
            st.rerun()

ok = [q for q in quotes if q.ok]
if not ok:
    st.stop()

# ---- 4. 결과 -----------------------------------------------------------------
with st.container(border=True):
    st.subheader("4. 결과")
    best = ok[0]
    m1, m2, m3 = st.columns(3)
    m1.metric("개당 착지가가 가장 낮은 곳", best.dest.name)
    m2.metric("개당 착지가", f"{fmt(best.per_unit_krw, 1)}원")
    m3.metric("총 착지가", f"{fmt(best.landed_krw)}원")

    table = pd.DataFrame([{
        "목적지": q.dest.name + ("" if q.dest.verified else " · 확인 필요"),
        "과세 기준": q.dest.rule.basis,
        "관세율": f"{q.duty_rate}%",
        "세율 근거": q.rate_note,
        "관세+세금(현지)": f"{fmt(q.result.duty + q.result.taxes, 2)} {q.currency}",
        "착지가(현지)": f"{fmt(q.result.landed, 2)} {q.currency}",
        "착지가(원)": fmt(q.landed_krw),
        "개당(원)": fmt(q.per_unit_krw, 1),
    } for q in ok])
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.caption(f"환율: {rates.source} · 기준일 {rates.as_of}. 금액은 계산 중 반올림하지 않고 표시할 때만 반올림합니다.")

    pick = st.selectbox("계산 과정 보기", [q.dest.key for q in ok], format_func=lambda k: DESTS[k].name)
    q = next(x for x in ok if x.dest.key == pick)
    try:
        import plotly.graph_objects as go
        steps = [l for l in q.result.lines if l.amount]
        fig = go.Figure(go.Waterfall(
            orientation="v", measure=["relative"] * len(steps) + ["total"],
            x=[l.label for l in steps] + ["착지가"],
            y=[float(l.amount) for l in steps] + [0],
            text=[fmt(l.amount) for l in steps] + [fmt(q.result.landed)], textposition="outside",
            connector={"line": {"color": "#c9cfc7"}},
            increasing={"marker": {"color": "#5b7fa6"}}, totals={"marker": {"color": "#d2901a"}}))
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), yaxis_title=q.currency, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        pass
    st.dataframe(pd.DataFrame([{"항목": l.label, f"금액({q.currency})": fmt(l.amount, 2), "계산": l.note}
                               for l in q.result.lines]), hide_index=True, use_container_width=True)
    for c in q.cautions:
        st.caption("· " + c)
    if q.tariff:
        st.caption(f"관세율 출처: {q.tariff.get('source')} ({q.tariff.get('as_of')}) · 국가 세번 {q.tariff.get('national_code')}")

    # PDF
    from report.pdf import build_pdf
    pdf = build_pdf(
        product=ss.product or ss.desc, hs6=hs6, hs_name=CATALOG[hs6]["name"], quantity=quantity, input_currency=currency,
        rows=[{"name": x.dest.name, "currency": x.currency, "duty_rate": f"{x.duty_rate}%", "landed_local": x.result.landed,
               "landed_krw": x.landed_krw, "per_unit_krw": x.per_unit_krw, "flag": not x.dest.verified} for x in ok],
        detail={"name": q.dest.name, "currency": q.currency, "lines": [(l.label, l.amount, l.note) for l in q.result.lines],
                "landed_local": q.result.landed, "landed_krw": q.landed_krw},
        rates_note=f"환율 {rates.source} {rates.as_of}",
        caveats=[f"HS {hs6[:4]}.{hs6[4:]}는 참고용 후보입니다. 확정은 관세사 또는 품목분류 사전심사로 하세요.",
                 "FTA 세율은 원산지 요건을 충족하고 원산지증명서를 갖췄을 때만 적용됩니다." if fta_ok else "FTA 세율을 적용하지 않았습니다.",
                 "수입 부가세를 비용에 포함했습니다." if include_vat else "수입 부가세는 공제받는다고 보고 비용에서 뺐습니다.",
                 "내륙 운송비, 현지 유통 마진, 인증·등록 비용은 포함하지 않았습니다."] + list(q.cautions)[:3])
    st.download_button("견적 리포트 PDF 내려받기", pdf, file_name=f"landed_cost_{hs6}.pdf", mime="application/pdf")

with st.expander("데이터 출처와 한계"):
    st.markdown(
        "- 관세율: BEAUPORT 관세·통관 탭에서 직접 정리한 데이터(HS 3304 소호, 7개 권역). 다른 HS는 직접 입력합니다.\n"
        "- 과세 기준·부가세율: `data/tax_rules.json`. ‘확인 필요’ 표시가 붙은 목적지는 공식 출처 확인이 필요합니다.\n"
        "- 환율: ExchangeRate-API(키가 있을 때) 또는 등록 환율.\n"
        "- 소액 면세, 전자상거래 특례, 반덤핑·세이프가드 관세는 다루지 않습니다.")
