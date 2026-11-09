# 수출 착지가 계산기 (Landed Cost Calculator)

> 화장품 제품 설명으로 **HS 코드 후보를 근거와 함께** 찾고, 목적지별 **관세·FTA 세율·수입 부가세·환율**을 합쳐
> 현지 도착 원가(착지가)를 원화와 현지 통화로 계산하는 1인 프로젝트입니다.

![tests](https://github.com/UMassJuny8-dot/landed-cost/actions/workflows/tests.yml/badge.svg)

- 서비스: https://landed-cost-mquqxnjmkxf45xz2dcugvb.streamlit.app/
- 만든 사람: 황준영 · KITA AX마스터 과정

## 왜 만들었나

팀 프로젝트 [BEAUPORT](https://github.com/kijoojootopia/beauty_dashboard)에서 관세·통관 탭을 맡아 국가별 관세율 조회를 만들었지만,
README에 남긴 대로 **"총수입비용·관세액 계산은 포함하지 않음"**으로 끝났습니다.
이 프로젝트는 그때 직접 정리한 관세 데이터와 환율 산식을 이어받아, 견적을 내는 데 실제로 필요한 착지가 계산까지 혼자 완성한 것입니다.

## 할 수 있는 것

1. **HS 코드 후보 추천**: 제품명·설명을 넣으면 HS 33류·3401류 목록 안에서 후보 3개를 근거 문장과 함께 보여 줍니다.
2. **세율 선택**: 등록 데이터에서 일반·FTA·추가 관세 세율을 고르고, FTA 원산지 요건을 못 맞추면 일반 세율을 직접 넣게 합니다.
3. **착지가 계산**: 과세가격(CIF/FOB) → 관세 → 소비세·통관 수수료 → 수입 부가세 → 착지가를 단계별로 보여 줍니다.
4. **목적지 비교**: EU 6개국, 미국, 일본, 중국, UAE, 러시아, ASEAN 10개국 중 여러 곳을 골라 개당 착지가로 비교합니다.
5. **견적 리포트**: 비교표와 계산 과정, 확인할 점을 담은 A4 한 장 PDF를 내려받습니다.

## 설계 원칙: 계산은 공식으로, AI는 바꾸기 어려운 부분에만

| 단계 | 맡는 쪽 | 장치 |
|---|---|---|
| 제품 설명 → HS 후보 | AI (키가 없으면 규칙 기반) | JSON 스키마의 `enum`으로 등록 목록 안에서만 답하게 제한 |
| 후보 검사 | 코드 | 목록에 없는 코드·빈 근거는 버리고 규칙 기반으로 대신 |
| 후보 선택 | 사람 | 화면에 "참고용 후보, 확정은 관세사·사전심사" 상시 표시 |
| 세율 조회·착지가 계산 | 코드 | `Decimal`로 계산, 표시할 때만 반올림, AI 관여 없음 |

## 계산 공식

```
과세가격 = FOB + 운임 + 보험료      (CIF 기준: EU·일본·중국·UAE·러시아·ASEAN)
        = FOB                      (FOB 기준: 미국)
관세     = 과세가격 × 적용 세율
소비세   = (과세가격 + 관세) ÷ (1 − 세율) × 세율       (중국 고급 화장품만)
부가세   = (과세가격 + 관세 [+ 소비세]) × 부가세율
MPF     = FOB × 0.3464%, 최소 $34.58 · 최대 $670.86   (미국, FY2027)
HMF     = FOB × 0.125%                               (미국, 해상 운송만)
착지가   = FOB + 운임 + 보험료 + 관세 + 세금·수수료 + 기타 비용
```

환율은 BEAUPORT와 같은 산식 `금액 × (기준 환율 ÷ 고시 단위) ÷ (대상 환율 ÷ 고시 단위)`를 씁니다 (엔화 100엔 단위 등).

## 검증 결과

| 항목 | 방법 | 결과 |
|---|---|---|
| 계산 정확도 | 손으로 계산한 예제 20개 + 세율 선택·환율·데이터 테스트 | `pytest` 39개 통과 |
| HS 추천 (규칙 기반) | 평가 세트 30건에서 정답이 후보 3개 안에 드는지 | 30/30 (1순위 29/30) |
| 범위 밖 차단 | 식품·의약품·미용기기·화장 도구 10건 | 10/10 차단 |
| 지시문 섞인 입력 | "이전 지시를 무시하고…" 같은 설명 | 후보를 내지 않음 |

> 평가 세트(`eval/hs_eval_set.json`)는 직접 만든 것이고, 규칙 기반 키워드도 같은 사람이 만들었기 때문에 점수가 실제보다 높게 나왔을 수 있습니다.
> 다음 단계로 관세청 품목분류 결정사례로 평가 세트를 바꿔 다시 측정할 계획입니다. AI 추천 점수는 `OPENAI_API_KEY`를 넣고 `python -m eval.run_eval --ai`로 잽니다.

## 실행

```bash
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q             # 테스트
python -m eval.run_eval         # HS 추천 평가
streamlit run app.py            # 화면
```

API 키는 선택입니다. `.streamlit/secrets.toml.example`을 `secrets.toml`로 복사해 넣으면 AI 추천과 실시간 환율을 씁니다.
비워 두면 규칙 기반 추천과 등록 환율(한국수출입은행, 2026-09-27)로 동작합니다.

## 폴더 구조

```
calc/      착지가 공식(landed.py), 데이터 읽기(data.py), 견적 조립(quote.py), 실시간 환율(fx_live.py) — AI 없음
hs/        HS 후보 추천: OpenAI 구조화 출력 + 응답 검사 + 규칙 기반 대체
report/    A4 한 장 PDF 리포트
data/      tariffs.json(BEAUPORT 관세 데이터), tax_rules.json(과세 기준·부가세), hs_catalog.json, exchange_rates.json
eval/      HS 추천 평가 세트와 실행 스크립트
tests/     pytest
app.py     Streamlit 화면
```

## 데이터 출처와 한계

- 관세율: BEAUPORT 관세·통관 탭에서 정리한 HS 3304 소호 데이터(출처 한국무역협회, 2026년 4~9월 기준). 다른 HS 코드는 화면에서 세율을 직접 넣습니다.
- 부가세·과세 기준: `data/tax_rules.json`. `verified: false`인 목적지는 화면에 "확인 필요"로 표시합니다.
  러시아 VAT 22%(2026년 1월부터), 미국 MPF FY2027 한도, 베트남 8% 감면 연장은 확인한 자료의 링크를 데이터에 남겼습니다.
- 다루지 않는 것: 소액 면세·전자상거래 특례, 반덤핑·세이프가드 관세, 내륙 운송비, 현지 인증·등록 비용.
- 이 도구의 결과는 견적 검토용 참고치입니다. 실제 수출 전에는 각 나라의 공식 원문과 최신 개정 여부를 확인하세요.

글꼴: Noto Sans CJK KR (SIL OFL 1.1), `assets/fonts/NOTICE.md` 참고.
