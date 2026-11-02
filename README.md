# Portfolio Analyzer

A web app for tracking and analyzing a personal investment portfolio: enter your holdings, see the allocation in a chart, compare your performance against 100% SPY / QQQM, and ask an analyst powered by **Google Gemini AI** questions about your portfolio. Available in **Hebrew and English**, with amounts in **shekels or dollars**.

![App screenshot](docs/screenshot.png)

---

## Features

### 📈 Real-time prices
- Prices for stocks, ETFs, crypto and more are fetched **in real time from the Yahoo Finance API** (`query1.finance.yahoo.com`).
- Any Yahoo symbol is supported: US stocks (`AAPL`, `SPY`), Tel Aviv Stock Exchange (`TEVA.TA`), crypto (`BTC-USD`) and more.
- **Automatic conversion to ILS (₪)** using the latest exchange rate (also from Yahoo). TASE shares priced in agorot are converted to shekels. Prices are stored in ILS and can be displayed in USD (see below).
- 60-second server-side cache to avoid overloading the data source.

### 🧩 Layout
- Three columns side by side on wide screens (1280px and up): **holdings** (add an asset + table, the widest column), **chart**, and **the analyst**.
- Medium screens: holdings and chart side by side, the analyst below at full width.
- The holdings table is compact (stacked edit / delete buttons, long type names wrap). If it is still wider than its column, for example with a very long asset name, it scrolls sideways inside its card - the page itself never does.
- Phones: one column; the holdings table also hides quantity and price (shown when editing), and the page never scrolls sideways.

### 🍩 Portfolio allocation chart
- A donut chart showing the **portfolio allocation in percentages**, with the total value in the center.
- Three views, each with its own title: **Asset allocation** (by asset), **Type allocation** (by asset type) and **Compare** (see below). The title and view buttons stay in place when switching.
- A holdings table with quantity, price, value and percentage of the portfolio, including edit and delete. Cash rows show only their value.
- Holdings are saved in a local **SQLite database**, so they persist across refreshes, browsers and server restarts.

### 🏷️ Asset types
- Supported types: **stocks, bonds, ETFs, mutual funds, crypto, cash** and **other**. The type is used for the "by type" view and by the analyst to assess risk and diversification.
- **Automatic detection:** when a symbol is found, the type is pre-selected from Yahoo's classification (stock, ETF, mutual fund, crypto). It can still be changed manually.
- **Bond funds** such as `BND`, `AGG` or `TLT` are ETFs that hold bonds, so they are detected as ETFs - change the type to "bonds" manually.
- **Cash** has its own form: a free-text name (e.g. a bank account) and a single amount in the selected currency, with no market lookup. It is stored in ILS.
- Assets that are not on Yahoo (e.g. Israeli mutual funds) can be added with a manually entered price.

### 📊 Performance comparison vs. SPY / QQQM
- A **"Compare"** view in the chart card answers: *would I have done better with 100% in SPY or 100% in QQQM?*
- A line chart of cumulative returns for **your portfolio**, **100% SPY** and **100% QQQM**, over **1 month, 6 months, 1 year or 5 years**, with a one-line summary (e.g. *"Over the last year, your portfolio returned +6.1% – less than SPY (+6.9%) and more than QQQM (+4.5%)."*).
- Hover the chart to see all three returns on any date.
- How it is calculated: the **current holdings** are assumed to be held for the whole period, and the same starting amount is put entirely into SPY or QQQM. Prices come from Yahoo Finance history, are **dividend-adjusted** (total return) and calculated in the **selected currency** (ILS or USD) with the historical exchange rate - so the returns are what an investor in that currency would see. Assets with no price history (e.g. cash) keep a constant ILS value.
- This is a backtest of today's allocation, not your actual profit (purchase dates and prices are not tracked yet).

### 🤖 The Analyst - powered by Gemini AI
- The "Analyst" panel lets you ask free-form questions about your portfolio, or pick a preset question (e.g. *"Is my portfolio too risky?"*, *"How can I improve diversification?"*).
- **Portfolio data is attached automatically to every question**: the server summarizes the holdings, values and allocation by type (in the selected currency), and sends them to Gemini together with the question.
- The analyst answers in the **selected language** (Hebrew or English).
- The analyst addresses diversification, risk level, currency exposure and liquidity, and ends with practical recommendations.
- If the primary model (`gemini-3.5-flash`) is overloaded, the server automatically falls back to a backup model (`gemini-3.5-flash-lite`).
- **Chat history with a smart context window** - see below.
- ⚠️ The analysis is for educational purposes only and is not investment advice.

### 💾 Database & chat memory (SQLite)
- All data is stored in `data/portfolio.db` (created automatically on first run, never committed).
- **Full chat history** is stored in the database and reloaded on page load, so conversations persist across refreshes.
- **Sliding context window:** only the **last 10 conversation turns** (a turn = a question + its answer) are sent to Gemini, together with the current portfolio. This keeps the analyst aware of earlier context (age, goals, follow-ups) while preventing context bloat and keeping latency low.
- A question and its answer are saved together, only after a successful reply, so the history never contains a question without an answer.
- A **"Clear conversation"** button wipes the chat history.
- Holdings saved in the browser by older versions are **imported automatically** on first load.

### 🌐 Hebrew / English
- A language switcher with **Israeli and US flags** at the top of the page switches the whole site between **Hebrew (right-to-left)** and **English (left-to-right)** in one click.
- Everything is translated: labels, buttons, messages, asset types, chart and comparison texts, number and date formats.
- **The analyst answers in the selected language.**
- The choice is remembered in the browser. Asset types are stored in one form in the database and only translated for display, so switching never affects saved data.
- Hebrew cash names are shown in English too (e.g. "עו״ש" → "Checking account"); the stored name does not change.

### 💱 Shekels / dollars
- A **₪ / $ switch** under the language switcher shows every amount in **shekels or dollars**: the table, the chart, the totals, the form, price lookups and the comparison.
- Dollar amounts use the **live USD/ILS rate** from Yahoo Finance (hover the $ button to see it).
- In dollar mode, prices and cash amounts are **entered in dollars** and converted to shekels when saved; values typed in the form are converted when switching.
- The **comparison is recalculated in the selected currency**, since returns differ between a shekel and a dollar investor when the exchange rate moves.
- The analyst gets the portfolio values in the selected currency. The choice is remembered in the browser.

---

## Usage

1. **Add an asset** - enter a symbol (e.g. `AAPL`) and the number of units. The price **and the asset type** (stock, ETF, mutual fund, crypto) are filled in automatically from the market; you can still change them or enter a price manually. For **cash**, choose the "Cash" type: the form switches to a free-text name (e.g. a bank account) and a single **amount** field.
2. **View the portfolio** - the chart and table update immediately. Switch between the "by asset" and "by type" views, or open **"Compare"** to see how the portfolio did against 100% SPY / QQQM.
3. **Switch language or currency** - click the Israeli or US flag, or ₪ / $, at the top of the page.
4. **Ask the analyst** - type a question (e.g. *"I'm 30 and investing long-term - what should I change?"*) and click **Ask the Analyst**.

---

## Installation & Running

Requirements: Python 3.10+

```bash
pip install -r requirements.txt
```

Create a `.env` file (based on `.env.example`) with a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey):

```
GEMINI_API_KEY=your-key-here
```

Start the server:

```bash
python server.py
```

Then open http://localhost:8000 in your browser.

> Without an API key the app works as usual (prices, charts and comparison); only the analyst is unavailable.

- **Another port:** set the `PORT` environment variable (e.g. `PORT=8001 python server.py`).
- **After changing `server.py`**, stop the server (Ctrl+C) and start it again. Changes to files in `public/` only need a browser refresh (Ctrl+Shift+R).

---

## Database Schema

| Table | Columns |
|-------|---------|
| `portfolios` | `id` (PK), `name`, `created_at` |
| `holdings` | `id` (PK), `portfolio_id` (FK → portfolios), `symbol`, `asset_type`, `quantity`, `unit_price` |
| `chat_messages` | `id` (PK), `portfolio_id` (FK → portfolios), `role` (`user` \| `assistant`), `content`, `created_at` |

A **"Default Portfolio"** is created automatically on first run. `unit_price` is the last known price in ILS (from Yahoo Finance or entered manually).

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/quote?symbol=AAPL` | Live price from Yahoo Finance, converted to ILS, plus the asset class (`instrumentType`). Also used for the USD/ILS rate (`USDILS=X`) |
| `GET` | `/api/compare?range=1y&currency=ILS` | Portfolio vs. 100% SPY / 100% QQQM returns (`range`: `1mo`, `6mo`, `1y`, `5y`; `currency`: `ILS`, `USD`) |
| `GET` | `/api/portfolio` | The portfolio and its holdings |
| `POST` | `/api/holdings` | Add a holding |
| `PUT` | `/api/holdings/<id>` | Update a holding |
| `DELETE` | `/api/holdings/<id>` | Delete a holding |
| `POST` | `/api/holdings/import` | One-time import of browser-saved holdings (only if the portfolio is empty) |
| `POST` | `/api/analyze` | Ask the analyst (`{"question": "...", "lang": "he", "currency": "ILS"}`) |
| `GET` | `/api/history?limit=100` | Recent chat messages |
| `DELETE` | `/api/history` | Clear the chat history |
| `GET` | `/api/status` | Whether the analyst (API key) is available |

## Project Structure

```
Portfolio-Analyzer/
├── public/              # Front end (the only folder served to the browser)
│   ├── index.html       # Page structure
│   ├── styles.css       # Styling (light and dark mode)
│   ├── i18n.js          # Hebrew / English translations and language switching
│   └── app.js           # Client-side logic: holdings, charts, currency, API calls
├── docs/
│   └── screenshot.png   # Screenshot used in this README
├── data/                # Created at runtime - SQLite database portfolio.db (not committed)
├── server.py            # Python server: static files, REST API, SQLite data layer, Gemini & Yahoo Finance
├── requirements.txt     # Python dependencies
├── .env.example         # Template for your .env file (API key settings)
└── .gitignore
```

> `.env` holds your private API key and is never committed - only `.env.example` (an empty template) is in the repo.

## Tech Stack

- **Frontend:** HTML, CSS, JavaScript (no libraries)
- **Backend:** Python (`http.server`)
- **Market data:** Yahoo Finance API
- **AI:** Google Gemini (`google-genai`)
- **Database:** SQLite (built into Python, no setup needed)
