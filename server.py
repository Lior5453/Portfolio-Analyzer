"""Local server for the Portfolio Analyzer web app.

Serves the site's static files and adds API endpoints, for example:
  GET /api/quote?symbol=AAPL
which returns the current market price (from Yahoo Finance) and the price converted to ILS.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

PORT = int(os.environ.get("PORT", 8000))
HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(HERE, "public")  # only this folder is served to the browser


def load_env_file():
    """Loads variables from the .env file next to the server (if present), without overriding existing environment variables."""
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()

# ---------- Analyst (Google Gemini) ----------
# The model can be changed via GEMINI_MODEL in the .env file.
# If the primary model is overloaded or times out, we automatically fall back to the backup model.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
FALLBACK_MODEL = "gemini-3.5-flash-lite"
REQUEST_TIMEOUT_MS = 45_000
RETRYABLE_CODES = {429, 500, 503, 504}
ANALYST_SYSTEM = """You are an experienced investment analyst helping a private user understand the state of their investment portfolio.
With every request you receive the current portfolio data (assets, types, values and percentages) and the user's question.

How to answer:
- Write in Hebrew, in simple and clear language.
- Base your analysis on the actual data: cite numbers and percentages from the portfolio.
- Address diversification (concentration in a single asset or asset type), risk level, currency exposure and liquidity, as relevant to the question.
- End with practical, numbered recommendations: what you would consider doing with the portfolio and why.
- If important information is missing (investment horizon, goals, risk tolerance), state which assumptions you made.
- Use short headings (##), lists and **bold** to keep it easy to read. No tables.
- This is an educational analysis, not licensed investment advice; say so in one short sentence at the end."""

_client = None


def gemini_client():
    global _client
    if _client is None:
        # The library reads the key from GEMINI_API_KEY (or GOOGLE_API_KEY)
        _client = genai.Client(http_options=genai_types.HttpOptions(timeout=REQUEST_TIMEOUT_MS))
    return _client


def has_api_key():
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def portfolio_summary(holdings):
    """Turns the holdings list into structured text sent to Gemini (not shown to the user)."""
    rows, total = [], 0.0
    for h in holdings:
        try:
            qty, price = float(h["quantity"]), float(h["price"])
        except (KeyError, TypeError, ValueError):
            continue
        value = qty * price
        total += value
        rows.append((str(h.get("name", "?"))[:60], str(h.get("type", "?"))[:30], qty, price, value))
    if not rows:
        return "The portfolio is currently empty - it has no assets."

    lines = [f"Total value: ₪{total:,.2f}", "", "Holdings:"]
    for name, typ, qty, price, value in sorted(rows, key=lambda r: -r[4]):
        share = value / total * 100 if total else 0
        lines.append(f"- {name} | type: {typ} | quantity: {qty:g} | unit price: ₪{price:,.2f} | value: ₪{value:,.2f} | {share:.1f}% of portfolio")

    by_type = {}
    for _, typ, _, _, value in rows:
        by_type[typ] = by_type.get(typ, 0) + value
    lines += ["", "Allocation by asset type:"]
    for typ, value in sorted(by_type.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {typ}: {value / total * 100:.1f}% (₪{value:,.2f})")
    return "\n".join(lines)


def analyze(question, holdings):
    content = (
        f"<portfolio>\n{portfolio_summary(holdings)}\n</portfolio>\n\n"
        f"<question>\n{question}\n</question>"
    )
    config = genai_types.GenerateContentConfig(
        system_instruction=ANALYST_SYSTEM,
        max_output_tokens=16000,
    )
    models = [MODEL] + ([FALLBACK_MODEL] if FALLBACK_MODEL != MODEL else [])
    for i, model in enumerate(models):
        is_last = i == len(models) - 1
        try:
            response = gemini_client().models.generate_content(model=model, contents=content, config=config)
        except genai_errors.APIError as e:
            if e.code in RETRYABLE_CODES and not is_last:
                print(f"[analyst] {model} returned {e.code}, falling back")
                continue
            raise
        except Exception as e:  # timeout / network error
            if not is_last:
                print(f"[analyst] {model} failed ({type(e).__name__}), falling back")
                continue
            raise
        text = response.text  # None when the response was blocked or empty
        return text.strip() if text else None
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
CACHE_SECONDS = 60
_cache = {}  # symbol -> (time, data)


def fetch_meta(symbol):
    """Returns the asset's meta data from Yahoo, or None if not found."""
    now = time.time()
    hit = _cache.get(symbol)
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]
    url = YAHOO_URL.format(urllib.parse.quote(symbol))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.load(r)["chart"]["result"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    meta = result[0]["meta"] if result else None
    if meta and meta.get("regularMarketPrice") is None:
        meta = None
    _cache[symbol] = (now, meta)
    return meta


def quote(symbol):
    meta = fetch_meta(symbol)
    if not meta:
        return None
    price = float(meta["regularMarketPrice"])
    currency = (meta.get("currency") or "USD").upper()

    # Tel Aviv Stock Exchange shares are priced in agorot (ILA)
    if currency == "ILA":
        price_ils = price / 100
        currency, price = "ILS", price / 100
    elif currency == "ILS":
        price_ils = price
    else:
        fx = fetch_meta(f"{currency}ILS=X")
        if not fx:
            raise RuntimeError(f"no exchange rate for {currency}")
        price_ils = price * float(fx["regularMarketPrice"])

    return {
        "symbol": meta.get("symbol", symbol),
        "name": meta.get("longName") or meta.get("shortName") or symbol,
        "price": round(price, 4),
        "currency": currency,
        "priceILS": round(price_ils, 4),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def do_POST(self):
        if self.path != "/api/analyze":
            return self.send_json(404, {"error": "not found"})
        if not has_api_key():
            return self.send_json(503, {"error": "no_api_key"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(min(length, 200_000)) or b"{}")
            question = str(body.get("question", "")).strip()[:4000]
            holdings = body.get("holdings") or []
            if not isinstance(holdings, list):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {"error": "bad request"})
        if not question:
            question = "Give me a general analysis of my portfolio and what you would recommend doing with it."

        try:
            answer = analyze(question, holdings[:200])
        except genai_errors.APIError as e:
            if e.code in (400, 401, 403) and "key" in str(e).lower():
                return self.send_json(401, {"error": "bad_api_key"})
            if e.code == 429:
                return self.send_json(429, {"error": "rate_limited"})
            return self.send_json(502, {"error": f"api_error {e.code}"})
        except Exception as e:  # timeout / network error
            print(f"[analyst] failed: {type(e).__name__}: {e}")
            return self.send_json(504, {"error": "timeout"})
        if answer is None:
            return self.send_json(422, {"error": "refused"})
        self.send_json(200, {"answer": answer})

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            return self.send_json(200, {"analyst": has_api_key()})
        if parsed.path != "/api/quote":
            return super().do_GET()
        symbol = urllib.parse.parse_qs(parsed.query).get("symbol", [""])[0].strip().upper()
        if not symbol:
            return self.send_json(400, {"error": "missing symbol"})
        try:
            data = quote(symbol)
        except Exception as e:  # network / data source error
            return self.send_json(502, {"error": str(e)})
        if not data:
            return self.send_json(404, {"error": "not found"})
        self.send_json(200, data)

    def send_json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    print(f"Serving on http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
