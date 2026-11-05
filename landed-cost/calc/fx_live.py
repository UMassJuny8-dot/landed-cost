"""ExchangeRate-API에서 원화 기준 환율을 받아 옵니다. 키가 없으면 등록 환율을 씁니다."""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal

from .data import Rates, registered_rates

URL = "https://v6.exchangerate-api.com/v6/latest/KRW"


def live_rates(api_key: str | None, timeout: float = 8.0) -> tuple[Rates, str | None]:
    """(환율, 경고 문구) 를 돌려줍니다. 실패하면 등록 환율과 이유를 돌려줍니다."""
    if not api_key:
        return registered_rates(), None
    try:
        req = urllib.request.Request(URL, headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        if body.get("result") != "success" or body.get("base_code") != "KRW":
            raise ValueError(body.get("error-type", "응답 형식 오류"))
        as_of = datetime.fromtimestamp(body["time_last_update_unix"], timezone.utc).date().isoformat()
        table = {}
        for cur, value in body["conversion_rates"].items():
            v = Decimal(str(value))
            if v > 0 and len(cur) == 3:
                table[cur] = (1 / v, Decimal(1))  # 1 통화 = 1/v 원
        table.setdefault("CNH", table.get("CNY"))
        return Rates(as_of=as_of, source="ExchangeRate-API", table={k: v for k, v in table.items() if v}), None
    except Exception as error:  # 네트워크·키 오류 모두 등록 환율로 대신합니다.
        return registered_rates(), f"실시간 환율을 불러오지 못해 등록 환율을 씁니다 ({error})."
