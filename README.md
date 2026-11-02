# Portfolio Analyzer

A web app for tracking and analyzing a personal investment portfolio: enter your holdings, see the allocation in a chart, and ask an analyst powered by **Google Gemini AI** questions about your portfolio.

![App screenshot](docs/screenshot.png)

---

## Current State (Phase 1)

### 📈 Real-time prices
- Prices for stocks, ETFs, crypto and more are fetched **in real time from the Yahoo Finance API** (`query1.finance.yahoo.com`).
- Any Yahoo symbol is supported: US stocks (`AAPL`, `SPY`), Tel Aviv Stock Exchange (`TEVA.TA`), crypto (`BTC-USD`) and more.
- **Automatic conversion to ILS (₪)** using the latest exchange rate (also from Yahoo). TASE shares priced in agorot are converted to shekels.
- 60-second server-side cache to avoid overloading the data source.

### 🍩 Portfolio allocation chart
- A donut chart showing the **portfolio allocation in percentages**, with the total value in the center.
- Two views: **by asset** or **by asset type** (stocks, bonds, crypto...).
- A holdings table with quantity, price, value and percentage of the portfolio, including edit and delete.
- Holdings are saved in the browser (localStorage), so they persist after a refresh.

### 🤖 The Analyst - powered by Gemini AI
- The "Analyst" panel lets you ask free-form questions about your portfolio, or pick a preset question (e.g. *"Is my portfolio too risky?"*, *"How can I improve diversification?"*).
- **Portfolio data is attached automatically to every question**: the server summarizes the holdings, values and allocation by type, and sends them to Gemini together with the question.
- The analyst addresses diversification, risk level, currency exposure and liquidity, and ends with practical recommendations.
- If the primary model (`gemini-3.5-flash`) is overloaded, the server automatically falls back to a backup model (`gemini-3.5-flash-lite`).
- ⚠️ The analysis is for educational purposes only and is not investment advice.

> The app's interface is in Hebrew (RTL).

---

## Usage

1. **Add an asset** - enter a name/symbol (e.g. `AAPL`), choose the asset type and the number of units. The price is fetched automatically from the market (you can also enter it manually).
2. **View the portfolio** - the chart and table update immediately. Switch between the "by asset" and "by type" views.
3. **Ask the analyst** - type a question (e.g. *"I'm 30 and investing long-term - what should I change?"*) and click **Ask the Analyst**.

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

> Without an API key the app works as usual (prices and chart); only the analyst is unavailable.

---

## Project Structure

```
Portfolio-Analyzer/
├── public/              # Front end (the only folder served to the browser)
│   ├── index.html       # Page structure (RTL, Hebrew UI)
│   ├── styles.css       # Styling (dark mode)
│   └── app.js           # Client-side logic: holdings, chart, API calls
├── docs/
│   └── screenshot.png   # Screenshot used in this README
├── server.py            # Python server: serves public/, /api/quote (Yahoo Finance), /api/analyze (Gemini)
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
