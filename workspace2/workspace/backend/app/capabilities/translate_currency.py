"""
capabilities/translate_currency.py

- translate()         via LibreTranslate. The official hosted instance now
  requires a paid key for production use -- true zero-cost, keyless
  translation needs your own self-hosted instance
  (`docker run -p 5000:5000 libretranslate/libretranslate`), so `base_url`
  is configurable and defaults to localhost.
- convert_currency()  via exchangerate.host. This service has changed its
  free-tier key policy before, so this fails soft with a clear message
  rather than assuming a key is or isn't currently required.
"""

from __future__ import annotations

from typing import Optional

import requests


def translate(text: str, target_lang: str, source_lang: str = "auto", base_url: str = "http://localhost:5000") -> str:
    try:
        r = requests.post(
            f"{base_url}/translate",
            json={"q": text, "source": source_lang, "target": target_lang, "format": "text"},
            timeout=8,
        )
        r.raise_for_status()
        return r.json().get("translatedText", text)
    except requests.RequestException:
        return (
            "I couldn't reach a LibreTranslate instance -- point `base_url` at "
            "your own self-hosted instance (the public hosted one now needs a paid key)."
        )


def convert_currency(amount: float, from_ccy: str, to_ccy: str, api_key: Optional[str] = None) -> str:
    try:
        params = {"base": from_ccy, "symbols": to_ccy}
        if api_key:
            params["access_key"] = api_key
        r = requests.get("https://api.exchangerate.host/latest", params=params, timeout=6)
        r.raise_for_status()
        data = r.json()
        rate = data.get("rates", {}).get(to_ccy)
        if rate is None:
            return "That currency pair didn't come back from the exchange rate service -- double-check the codes."
        converted = amount * rate
        return f"{amount:.2f} {from_ccy} \u2248 {converted:.2f} {to_ccy}"
    except requests.RequestException:
        return (
            "The exchange rate service isn't reachable, or may now need a free "
            "API key -- add one in Settings > APIs if this keeps failing."
        )
