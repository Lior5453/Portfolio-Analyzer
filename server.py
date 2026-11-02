"""Local server for the Portfolio Analyzer web app.

Serves the site's static files (public/) and adds API endpoints:
  GET    /api/status               whether the analyst (Gemini API key) is available
  GET    /api/quote?symbol=AAPL    current market price (Yahoo Finance) and the price in ILS
  GET    /api/compare?range=1y&currency=ILS   portfolio performance vs. 100% SPY / 100% QQQM
                                     (range: 1mo, 6mo, 1y, 5y; currency: ILS or USD)
  GET    /api/portfolio            the default portfolio and its holdings
  POST   /api/holdings             add a holding
  PUT    /api/holdings/<id>        update a holding
  DELETE /api/holdings/<id>        delete a holding
  POST   /api/holdings/import      one-time import of holdings saved by older versions (browser storage)
  POST   /api/analyze              ask the analyst a question about the portfolio
  GET    /api/history?limit=N      recent chat messages (for display after a page refresh)
  DELETE /api/history              clear the chat history

Data is stored in a local SQLite database (data/portfolio.db).
"""
import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

PORT = int(os.environ.get("PORT", 8000))
HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(HERE, "public")  # only this folder is served to the browser
DB_PATH = os.path.join(HERE, "data", "portfolio.db")
DEFAULT_PORTFOLIO_NAME = "Default Portfolio"
CASH_ASSET_TYPE = "מזומן"  # the "cash" option value used by the UI's asset-type list

# Context window: only the last CONTEXT_TURNS turns are sent to Gemini.
# One turn = one user message + the assistant's reply. The full history stays in the database.
CONTEXT_TURNS = 10
HISTORY_DISPLAY_LIMIT = 100  # default number of messages returned to the UI
MAX_BODY_BYTES = 200_000
DEFAULT_QUESTION = "Give me a general analysis of my portfolio and what you would recommend doing with it."


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


# ======================================================================
# Database (SQLite)
# ======================================================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS holdings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    symbol       TEXT NOT NULL,
    asset_type   TEXT NOT NULL,
    quantity     REAL NOT NULL CHECK (quantity >= 0),
    unit_price   REAL NOT NULL DEFAULT 0 CHECK (unit_price >= 0)  -- last known price in ILS (Yahoo or manual)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    role         TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content      TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_holdings_portfolio ON holdings(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_chat_portfolio ON chat_messages(portfolio_id, id);
"""

HOLDING_COLUMNS = "id, portfolio_id, symbol, asset_type, quantity, unit_price"


@contextmanager
def get_connection():
    """Yields a connection that commits on success, rolls back on error, and is always closed.

    A new connection is opened per call, which is safe with the multi-threaded HTTP server.
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Creates the tables (if missing) and seeds the default portfolio."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT 1 FROM portfolios LIMIT 1").fetchone() is None:
            conn.execute("INSERT INTO portfolios (name) VALUES (?)", (DEFAULT_PORTFOLIO_NAME,))


def get_default_portfolio_id(conn):
    """Returns the id of the default (first) portfolio, creating it if needed."""
    row = conn.execute("SELECT id FROM portfolios ORDER BY id LIMIT 1").fetchone()
    if row:
        return row["id"]
    return conn.execute("INSERT INTO portfolios (name) VALUES (?)", (DEFAULT_PORTFOLIO_NAME,)).lastrowid


# ---------- Portfolio & holdings ----------
def get_portfolio():
    """Returns the default portfolio with its holdings (in insertion order)."""
    with get_connection() as conn:
        portfolio_id = get_default_portfolio_id(conn)
        portfolio = dict(conn.execute(
            "SELECT id, name, created_at FROM portfolios WHERE id = ?", (portfolio_id,)
        ).fetchone())
        portfolio["holdings"] = [dict(r) for r in conn.execute(
            f"SELECT {HOLDING_COLUMNS} FROM holdings WHERE portfolio_id = ? ORDER BY id", (portfolio_id,)
        )]
    return portfolio


def list_holdings():
    return get_portfolio()["holdings"]


def validate_holding(data):
    """Validates and normalizes holding fields from a request body. Raises ValueError on bad input."""
    if not isinstance(data, dict):
        raise ValueError("holding must be an object")
    asset_type = str(data.get("asset_type", "")).strip()[:30]
    symbol = str(data.get("symbol", "")).strip()[:60]
    if asset_type != CASH_ASSET_TYPE:
        symbol = symbol.upper()  # market symbols are uppercase; cash names are free text
    try:
        quantity = float(data.get("quantity"))
        unit_price = float(data.get("unit_price", 0) or 0)
    except (TypeError, ValueError):
        raise ValueError("quantity and unit_price must be numbers")
    if not symbol or not asset_type:
        raise ValueError("symbol and asset_type are required")
    if quantity < 0 or unit_price < 0:
        raise ValueError("quantity and unit_price must be non-negative")
    return {"symbol": symbol, "asset_type": asset_type, "quantity": quantity, "unit_price": unit_price}


def create_holding(fields):
    with get_connection() as conn:
        portfolio_id = get_default_portfolio_id(conn)
        holding_id = conn.execute(
            "INSERT INTO holdings (portfolio_id, symbol, asset_type, quantity, unit_price) VALUES (?, ?, ?, ?, ?)",
            (portfolio_id, fields["symbol"], fields["asset_type"], fields["quantity"], fields["unit_price"]),
        ).lastrowid
        return dict(conn.execute(f"SELECT {HOLDING_COLUMNS} FROM holdings WHERE id = ?", (holding_id,)).fetchone())


def update_holding(holding_id, fields):
    """Updates a holding. Returns the updated row, or None if it does not exist."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE holdings SET symbol = ?, asset_type = ?, quantity = ?, unit_price = ? WHERE id = ?",
            (fields["symbol"], fields["asset_type"], fields["quantity"], fields["unit_price"], holding_id),
        )
        if cursor.rowcount == 0:
            return None
        return dict(conn.execute(f"SELECT {HOLDING_COLUMNS} FROM holdings WHERE id = ?", (holding_id,)).fetchone())


def delete_holding(holding_id):
    """Deletes a holding. Returns True if a row was deleted."""
    with get_connection() as conn:
        return conn.execute("DELETE FROM holdings WHERE id = ?", (holding_id,)).rowcount > 0


def import_holdings(items):
    """Imports holdings into the default portfolio, only if it is still empty (one-time migration).

    Returns the number of imported holdings.
    """
    holdings = [validate_holding(item) for item in items[:200]]
    with get_connection() as conn:
        portfolio_id = get_default_portfolio_id(conn)
        if conn.execute("SELECT 1 FROM holdings WHERE portfolio_id = ? LIMIT 1", (portfolio_id,)).fetchone():
            return 0
        conn.executemany(
            "INSERT INTO holdings (portfolio_id, symbol, asset_type, quantity, unit_price) VALUES (?, ?, ?, ?, ?)",
            [(portfolio_id, h["symbol"], h["asset_type"], h["quantity"], h["unit_price"]) for h in holdings],
        )
    return len(holdings)


# ---------- Chat messages ----------
def get_recent_messages(limit):
    """Returns the last `limit` chat messages of the default portfolio, oldest first."""
    with get_connection() as conn:
        portfolio_id = get_default_portfolio_id(conn)
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM chat_messages "
            "WHERE portfolio_id = ? ORDER BY id DESC LIMIT ?",
            (portfolio_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_context_window():
    """Returns the sliding window sent to Gemini: the last CONTEXT_TURNS turns (user + assistant)."""
    messages = get_recent_messages(CONTEXT_TURNS * 2)
    # The window must start with a user message.
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return messages


def save_turn(question, answer):
    """Saves the user question and the assistant answer together, in one transaction."""
    with get_connection() as conn:
        portfolio_id = get_default_portfolio_id(conn)
        conn.executemany(
            "INSERT INTO chat_messages (portfolio_id, role, content) VALUES (?, ?, ?)",
            [(portfolio_id, "user", question), (portfolio_id, "assistant", answer)],
        )


def clear_chat_history():
    with get_connection() as conn:
        conn.execute("DELETE FROM chat_messages WHERE portfolio_id = ?", (get_default_portfolio_id(conn),))


# ======================================================================
# Display currency
# ======================================================================
# Prices are stored in ILS. The UI can show them in ILS or USD; USD values use the live rate.
CURRENCIES = {"ILS": "₪", "USD": "$"}
USD_ILS_SYMBOL = "USDILS=X"  # Yahoo symbol for the dollar / shekel exchange rate


def parse_currency(value):
    return value if value in CURRENCIES else "ILS"


def ils_per_unit(currency):
    """How many shekels one unit of the display currency is worth (1 for ILS)."""
    if currency == "ILS":
        return 1.0
    meta = fetch_meta(USD_ILS_SYMBOL)
    if not meta:
        raise RuntimeError("no USD/ILS exchange rate")
    return float(meta["regularMarketPrice"])


# ======================================================================
# Analyst (Google Gemini)
# ======================================================================
# The model can be changed via GEMINI_MODEL in the .env file.
# If the primary model is overloaded or times out, we automatically fall back to the backup model.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
FALLBACK_MODEL = "gemini-3.5-flash-lite"
REQUEST_TIMEOUT_MS = 45_000
RETRYABLE_CODES = {429, 500, 503, 504}
ANALYST_SYSTEM = """You are an experienced investment analyst helping a private user understand the state of their investment portfolio.
With every request you receive the current portfolio data (assets, types, values and percentages) and the user's question.

How to answer:
- Write in {language}, in simple and clear language (even if earlier messages were in another language).
- Base your analysis on the actual data: cite numbers and percentages from the portfolio.
- Address diversification (concentration in a single asset or asset type), risk level, currency exposure and liquidity, as relevant to the question.
- End with practical, numbered recommendations: what you would consider doing with the portfolio and why.
- If important information is missing (investment horizon, goals, risk tolerance), state which assumptions you made.
- Use short headings (##), lists and **bold** to keep it easy to read. No tables.
- This is an educational analysis, not licensed investment advice; say so in one short sentence at the end.

Earlier messages in the conversation are your recent exchanges with this user. Use them for context
(e.g. the user's age, goals or follow-up questions), but always analyze the portfolio data attached to the
latest question - it is the current state and may differ from earlier ones."""

_client = None


def gemini_client():
    global _client
    if _client is None:
        # The library reads the key from GEMINI_API_KEY (or GOOGLE_API_KEY)
        _client = genai.Client(http_options=genai_types.HttpOptions(timeout=REQUEST_TIMEOUT_MS))
    return _client


def has_api_key():
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def portfolio_summary(holdings, currency="ILS"):
    """Turns the holdings list into structured text sent to Gemini (not shown to the user).

    Amounts are shown in the display currency the user selected.
    """
    sign, rate = CURRENCIES[currency], ils_per_unit(currency)
    rows, total = [], 0.0
    for h in holdings:
        qty, price = float(h["quantity"]), float(h["unit_price"]) / rate
        value = qty * price
        total += value
        rows.append((h["symbol"], h["asset_type"], qty, price, value))
    if not rows:
        return "The portfolio is currently empty - it has no assets."

    lines = [f"Currency: {currency}", f"Total value: {sign}{total:,.2f}", "", "Holdings:"]
    for symbol, asset_type, qty, price, value in sorted(rows, key=lambda r: -r[4]):
        share = value / total * 100 if total else 0
        lines.append(f"- {symbol} | type: {asset_type} | quantity: {qty:g} | unit price: {sign}{price:,.2f} | value: {sign}{value:,.2f} | {share:.1f}% of portfolio")

    by_type = {}
    for _, asset_type, _, _, value in rows:
        by_type[asset_type] = by_type.get(asset_type, 0) + value
    lines += ["", "Allocation by asset type:"]
    for asset_type, value in sorted(by_type.items(), key=lambda kv: -kv[1]):
        share = value / total * 100 if total else 0
        lines.append(f"- {asset_type}: {share:.1f}% ({sign}{value:,.2f})")
    return "\n".join(lines)


# UI language code -> the language the analyst answers in
ANSWER_LANGUAGES = {"he": "Hebrew", "en": "English"}


def build_contents(question, holdings, context_messages, currency="ILS"):
    """Builds the Gemini request: the context window, then the new question with the current portfolio."""
    contents = []
    for message in context_messages:
        role = "model" if message["role"] == "assistant" else "user"
        text = message["content"] or (DEFAULT_QUESTION if role == "user" else "")
        contents.append(genai_types.Content(role=role, parts=[genai_types.Part(text=text)]))
    contents.append(genai_types.Content(role="user", parts=[genai_types.Part(text=(
        f"<portfolio>\n{portfolio_summary(holdings, currency)}\n</portfolio>\n\n"
        f"<question>\n{question or DEFAULT_QUESTION}\n</question>"
    ))]))
    return contents


def analyze(question, holdings, context_messages, lang="he", currency="ILS"):
    """Asks Gemini. Returns the answer text, or None if the response was blocked or empty."""
    contents = build_contents(question, holdings, context_messages, currency)
    config = genai_types.GenerateContentConfig(
        system_instruction=ANALYST_SYSTEM.replace("{language}", ANSWER_LANGUAGES.get(lang, "Hebrew")),
        max_output_tokens=16000,
    )
    models = [MODEL] + ([FALLBACK_MODEL] if FALLBACK_MODEL != MODEL else [])
    for i, model in enumerate(models):
        is_last = i == len(models) - 1
        try:
            response = gemini_client().models.generate_content(model=model, contents=contents, config=config)
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


# ======================================================================
# Market data (Yahoo Finance)
# ======================================================================
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
        # Yahoo's asset class, e.g. EQUITY, ETF, MUTUALFUND, CRYPTOCURRENCY (used to pre-select the asset type)
        "instrumentType": meta.get("instrumentType"),
    }


# ---------- Historical comparison (portfolio vs. benchmarks) ----------
BENCHMARKS = ["SPY", "QQQM"]
# range key -> Yahoo "interval" (weekly points keep the 5-year chart light)
COMPARE_RANGES = {"1mo": "1d", "6mo": "1d", "1y": "1d", "5y": "1wk"}
HISTORY_CACHE_SECONDS = 600
_history_cache = {}  # (symbol, range) -> (time, data)


def fetch_history(symbol, range_key):
    """Returns {"times": [...], "prices": [...], "currency": str} from Yahoo, or None if not found.

    Uses dividend-adjusted closes when available, so returns include dividends (total return).
    Prices are in the asset's own currency (agorot are converted to shekels).
    """
    cache_key = (symbol, range_key)
    now = time.time()
    hit = _history_cache.get(cache_key)
    if hit and now - hit[0] < HISTORY_CACHE_SECONDS:
        return hit[1]

    query = urllib.parse.urlencode({"range": range_key, "interval": COMPARE_RANGES[range_key]})
    url = YAHOO_URL.format(urllib.parse.quote(symbol)) + "?" + query
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.load(r)["chart"]["result"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise

    data = None
    if result and result[0].get("timestamp"):
        chart = result[0]
        indicators = chart.get("indicators", {})
        adjusted = (indicators.get("adjclose") or [{}])[0].get("adjclose")
        closes = adjusted or (indicators.get("quote") or [{}])[0].get("close") or []
        currency = (chart["meta"].get("currency") or "USD").upper()
        scale = 0.01 if currency == "ILA" else 1.0
        points = [(t, p * scale) for t, p in zip(chart["timestamp"], closes) if p is not None]
        if points:
            data = {
                "times": [t for t, _ in points],
                "prices": [p for _, p in points],
                "currency": "ILS" if currency == "ILA" else currency,
            }
    _history_cache[cache_key] = (now, data)
    return data


def values_on_grid(times, values, grid):
    """Aligns a time series to the grid: each grid time takes the last known value at or before it.

    Grid times before the first data point take the first value (the asset is treated as flat).
    """
    out, j = [], 0
    for t in grid:
        while j + 1 < len(times) and times[j + 1] <= t:
            j += 1
        out.append(values[j])
    return out


def history_in_ils(symbol, range_key, grid):
    """Returns the asset's price in ILS for every grid time, or None if Yahoo has no history for it."""
    history = fetch_history(symbol, range_key)
    if not history:
        return None
    prices = values_on_grid(history["times"], history["prices"], grid)
    if history["currency"] != "ILS":
        fx = fetch_history(f"{history['currency']}ILS=X", range_key)
        if not fx:
            raise RuntimeError(f"no exchange rate history for {history['currency']}")
        rates = values_on_grid(fx["times"], fx["prices"], grid)
        prices = [p * r for p, r in zip(prices, rates)]
    return prices


def compare_portfolio(holdings, range_key, currency="ILS"):
    """Compares the current portfolio, held over the whole period, with 100% in each benchmark.

    Values are calculated in the display currency (ILS or USD), using the historical exchange
    rate, so the returns are what an investor in that currency would see.
    Returns cumulative returns (0.05 = +5%) per grid time.
    Holdings with no Yahoo history (e.g. cash or manual assets) keep a constant ILS value.
    """
    # The first benchmark's trading days form the shared time grid.
    base = fetch_history(BENCHMARKS[0], range_key)
    if not base:
        raise RuntimeError("no benchmark history")
    grid = base["times"]

    portfolio_values = [0.0] * len(grid)
    flat_symbols = []
    for h in holdings:
        prices = history_in_ils(h["symbol"], range_key, grid)
        if prices is None:
            prices = [h["unit_price"]] * len(grid)
            flat_symbols.append(h["symbol"])
        for i, p in enumerate(prices):
            portfolio_values[i] += h["quantity"] * p

    # ILS -> display currency, per grid time
    if currency == "ILS":
        rates = [1.0] * len(grid)
    else:
        fx = fetch_history(USD_ILS_SYMBOL, range_key)
        if not fx:
            raise RuntimeError("no USD/ILS exchange rate history")
        rates = values_on_grid(fx["times"], fx["prices"], grid)

    def in_currency(values):
        return [v / r for v, r in zip(values, rates)]

    def cumulative_returns(values):
        start = values[0]
        return [round(v / start - 1, 6) if start else 0.0 for v in values]

    portfolio_values = in_currency(portfolio_values)
    series = [{"key": "portfolio", "returns": cumulative_returns(portfolio_values)}]
    for symbol in BENCHMARKS:
        benchmark = in_currency(history_in_ils(symbol, range_key, grid))
        series.append({"key": symbol, "returns": cumulative_returns(benchmark)})

    return {
        "range": range_key,
        "times": grid,
        "series": series,
        "currency": currency,
        "start_value": round(portfolio_values[0], 2),
        "end_value": round(portfolio_values[-1], 2),
        "flat_symbols": flat_symbols,
    }


# ======================================================================
# HTTP handler
# ======================================================================
class BadRequest(Exception):
    pass


def parse_holding_id(path):
    """Returns the id from /api/holdings/<id>, or None if the path does not match."""
    prefix = "/api/holdings/"
    if path.startswith(prefix) and path[len(prefix):].isdigit():
        return int(path[len(prefix):])
    return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    # ---------- Routing ----------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return super().do_GET()
        self.handle_api(self.api_get, parsed)

    def do_POST(self):
        self.handle_api(self.api_post, urllib.parse.urlparse(self.path))

    def do_PUT(self):
        self.handle_api(self.api_put, urllib.parse.urlparse(self.path))

    def do_DELETE(self):
        self.handle_api(self.api_delete, urllib.parse.urlparse(self.path))

    def handle_api(self, method, parsed):
        """Runs an API method and turns common errors into JSON responses."""
        try:
            method(parsed)
        except BadRequest as e:
            self.send_json(400, {"error": "bad_request", "detail": str(e)})
        except sqlite3.Error as e:
            print(f"[db] {type(e).__name__}: {e}")
            self.send_json(500, {"error": "database_error"})

    def api_get(self, parsed):
        path = parsed.path
        if path == "/api/status":
            return self.send_json(200, {"analyst": has_api_key()})
        if path == "/api/portfolio":
            return self.send_json(200, get_portfolio())
        if path == "/api/history":
            params = urllib.parse.parse_qs(parsed.query)
            try:
                limit = max(1, min(int(params.get("limit", [HISTORY_DISPLAY_LIMIT])[0]), 1000))
            except ValueError:
                raise BadRequest("limit must be a number")
            return self.send_json(200, {"messages": get_recent_messages(limit), "context_turns": CONTEXT_TURNS})
        if path == "/api/quote":
            return self.handle_quote(parsed)
        if path == "/api/compare":
            return self.handle_compare(parsed)
        self.send_json(404, {"error": "not found"})

    def api_post(self, parsed):
        path = parsed.path
        if path == "/api/analyze":
            return self.handle_analyze()
        if path == "/api/holdings":
            holding = create_holding(self.read_holding())
            return self.send_json(201, holding)
        if path == "/api/holdings/import":
            items = self.read_json().get("holdings")
            if not isinstance(items, list):
                raise BadRequest("holdings must be a list")
            try:
                imported = import_holdings(items)
            except ValueError as e:
                raise BadRequest(str(e))
            return self.send_json(200, {"imported": imported, "portfolio": get_portfolio()})
        self.send_json(404, {"error": "not found"})

    def api_put(self, parsed):
        holding_id = parse_holding_id(parsed.path)
        if holding_id is None:
            return self.send_json(404, {"error": "not found"})
        holding = update_holding(holding_id, self.read_holding())
        if holding is None:
            return self.send_json(404, {"error": "holding not found"})
        self.send_json(200, holding)

    def api_delete(self, parsed):
        if parsed.path == "/api/history":
            clear_chat_history()
            return self.send_json(200, {"ok": True})
        holding_id = parse_holding_id(parsed.path)
        if holding_id is None:
            return self.send_json(404, {"error": "not found"})
        if not delete_holding(holding_id):
            return self.send_json(404, {"error": "holding not found"})
        self.send_json(200, {"ok": True})

    # ---------- Handlers ----------
    def handle_quote(self, parsed):
        symbol = urllib.parse.parse_qs(parsed.query).get("symbol", [""])[0].strip().upper()
        if not symbol:
            raise BadRequest("missing symbol")
        try:
            data = quote(symbol)
        except Exception as e:  # network / data source error
            return self.send_json(502, {"error": str(e)})
        if not data:
            return self.send_json(404, {"error": "not found"})
        self.send_json(200, data)

    def handle_compare(self, parsed):
        params = urllib.parse.parse_qs(parsed.query)
        range_key = params.get("range", ["1y"])[0]
        currency = parse_currency(params.get("currency", ["ILS"])[0])
        if range_key not in COMPARE_RANGES:
            raise BadRequest(f"range must be one of: {', '.join(COMPARE_RANGES)}")
        holdings = list_holdings()
        if not holdings:
            return self.send_json(409, {"error": "empty_portfolio"})
        try:
            data = compare_portfolio(holdings, range_key, currency)
        except Exception as e:  # network / data source error
            print(f"[compare] failed: {type(e).__name__}: {e}")
            return self.send_json(502, {"error": "data_unavailable"})
        self.send_json(200, data)

    def handle_analyze(self):
        if not has_api_key():
            return self.send_json(503, {"error": "no_api_key"})
        body = self.read_json()
        question = str(body.get("question", "")).strip()[:4000]
        lang = body.get("lang") if body.get("lang") in ANSWER_LANGUAGES else "he"
        currency = parse_currency(body.get("currency"))
        # The portfolio and the context window are read from the database (the source of truth).
        holdings = list_holdings()
        context_messages = get_context_window()
        try:
            answer = analyze(question, holdings, context_messages, lang, currency)
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
        # Saved only after a successful answer, so the history never has a question without a reply.
        save_turn(question, answer)
        self.send_json(200, {"answer": answer})

    # ---------- Helpers ----------
    def read_json(self):
        """Reads and parses the JSON request body. Raises BadRequest on invalid input."""
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            raise BadRequest("invalid Content-Length")
        if length > MAX_BODY_BYTES:
            raise BadRequest("request body too large")
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise BadRequest("invalid JSON")
        if not isinstance(body, dict):
            raise BadRequest("JSON body must be an object")
        return body

    def read_holding(self):
        try:
            return validate_holding(self.read_json())
        except ValueError as e:
            raise BadRequest(str(e))

    def send_json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    init_db()
    print(f"Serving on http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
