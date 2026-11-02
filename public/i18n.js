// Translations (Hebrew / English) and language switching.
// Static page text uses data-i18n attributes; app.js uses t() for text it builds at runtime.
const LANG_STORAGE_KEY = "portfolio-lang";
const LANGS = { he: { dir: "rtl", locale: "he-IL" }, en: { dir: "ltr", locale: "en-US" } };

const I18N = {
  he: {
    pageTitle: "תיק ההשקעות שלי",
    subtitle: "הזן את האחזקות שלך וראה איך התיק מחולק",
    language: "שפה",

    // Holdings form
    addAsset: "הוספת נכס",
    nameLabel: "שם הנכס / סימול",
    namePlaceholder: "לדוגמה: AAPL, TEVA.TA, BTC-USD",
    cashNameLabel: "שם",
    cashNamePlaceholder: "לדוגמה: עו״ש, פיקדון, קופה",
    assetType: "סוג נכס",
    amount: "סכום (₪)",
    quantity: "כמות יחידות",
    unitPrice: "מחיר ליחידה (₪)",
    addToPortfolio: "הוסף לתיק",
    saveChanges: "שמור שינויים",
    cancelEdit: "ביטול עריכה",
    quoteSearching: "מחפש מחיר עדכני…",
    quoteNotFound: "לא נמצא נכס בסימול הזה – אפשר להזין מחיר ידנית",
    quoteFailed: "לא הצלחתי למשוך מחיר כרגע – אפשר להזין ידנית",
    loadFailed: "לא הצלחתי לטעון את התיק מהשרת. נסה לרענן את הדף.",
    saveFailed: "השמירה נכשלה. נסה שוב.",
    deleteFailed: "המחיקה נכשלה. נסה שוב.",

    // Holdings table
    myHoldings: "האחזקות שלי",
    colAsset: "נכס",
    colType: "סוג",
    colQty: "כמות",
    colPrice: "מחיר",
    colValue: "שווי",
    colShare: "אחוז",
    colActions: "פעולות",
    total: 'סה"כ',
    emptyHoldings: "עדיין אין נכסים בתיק. הוסף את הראשון למעלה.",
    edit: "עריכה",
    delete: "מחיקה",

    // Allocation chart
    allocationByAsset: "חלוקה לפי נכסים",
    allocationByType: "חלוקה לפי סוגים",
    chartView: "תצוגת הגרף",
    byAsset: "לפי נכס",
    byType: "לפי סוג",
    compare: "השוואה",
    donutAria: "גרף חלוקת התיק",
    portfolioValue: "שווי התיק",
    other: "אחר",

    // Performance comparison
    comparePerformance: "ביצועים",
    timeRange: "טווח זמן",
    range1mo: "חודש",
    range6mo: "6 חודשים",
    range1y: "שנה",
    range5y: "5 שנים",
    compareAria: "גרף השוואת תשואות",
    yourPortfolio: "התיק שלך",
    portfolioShort: "התיק",
    compareEmpty: "התיק ריק – הוסף נכסים כדי להשוות ביצועים.",
    compareLoading: "טוען נתוני מחירים היסטוריים…",
    compareFailed: "לא הצלחתי לטעון נתונים היסטוריים כרגע. נסה שוב בעוד רגע.",
    rangeSentence: { "1mo": "בחודש האחרון", "6mo": "ב-6 החודשים האחרונים", "1y": "בשנה האחרונה", "5y": "ב-5 השנים האחרונות" },
    verdictMore: (k, v) => `יותר מ-${k} (${v})`,
    verdictLess: (k, v) => `פחות מ-${k} (${v})`,
    verdictSame: (k, v) => `בדיוק כמו ${k} (${v})`,
    compareSummary: (range, mine, a, b) => `${range} התיק שלך השיג <strong>${mine}</strong> – ${a} ו${b}.`,
    compareNote: (amount) =>
      `ההשוואה מניחה שהתיק הנוכחי הוחזק לאורך כל התקופה, ושאותו סכום (${amount}) הושקע כולו ב-SPY או ב-QQQM. כולל דיבידנדים ושער הדולר, בשקלים.`,
    compareFlat: (list) => ` נכסים ללא נתונים היסטוריים נחשבו בערך קבוע: ${list}.`,

    // Analyst
    analyst: "האנליסט",
    analystIntro: "שאל שאלה על התיק. נתוני התיק מצורפים לשאלה אוטומטית.",
    chip1: "מה מצב התיק שלי ומה היית ממליץ לעשות?",
    chip2: "איך אפשר לשפר את הפיזור?",
    chip3: "האם התיק שלי מסוכן מדי?",
    yourQuestion: "השאלה שלך",
    questionPlaceholder: "לדוגמה: אני בן 30 ומשקיע לטווח ארוך – מה כדאי לשנות?",
    ask: "שאל את האנליסט",
    clearChat: "נקה שיחה",
    disclaimer: "הניתוח נוצר על ידי בינה מלאכותית, לצורכי לימוד בלבד, ואינו מהווה ייעוץ השקעות.",
    youAsked: "שאלת:",
    generalAnalysis: "ניתוח כללי של התיק",
    analyzing: "האנליסט בוחן את התיק שלך",
    historyLine: (max, n) => `השיחה נשמרת · האנליסט זוכר עד ${max} התכתבויות אחרונות (כרגע: ${n})`,
    confirmClear: "למחוק את כל השיחה עם האנליסט?",
    clearFailed: "לא הצלחתי למחוק את השיחה. נסה שוב.",
    analystEmpty: "התיק ריק – הוסף נכסים כדי שהאנליסט יוכל לנתח אותו.",
    analystGeneric: "משהו השתבש בפנייה לאנליסט. נסה שוב.",
    analystErrors: {
      no_api_key: "האנליסט עוד לא מחובר: צריך להוסיף מפתח API של Google Gemini לקובץ ‎.env‎ ולהפעיל מחדש את השרת.",
      bad_api_key: "מפתח ה-API לא תקין. בדוק את הקובץ ‎.env‎.",
      rate_limited: "יותר מדי בקשות כרגע. נסה שוב בעוד דקה.",
      timeout: "שירות ה-AI עמוס כרגע ולא ענה בזמן. נסה שוב בעוד כמה דקות.",
      refused: "האנליסט לא יכול לענות על השאלה הזו. נסה לנסח אותה אחרת.",
    },
  },

  en: {
    pageTitle: "My Investment Portfolio",
    subtitle: "Enter your holdings and see how your portfolio is allocated",
    language: "Language",

    addAsset: "Add an asset",
    nameLabel: "Asset name / symbol",
    namePlaceholder: "e.g. AAPL, TEVA.TA, BTC-USD",
    cashNameLabel: "Name",
    cashNamePlaceholder: "e.g. checking account, deposit, savings",
    assetType: "Asset type",
    amount: "Amount (₪)",
    quantity: "Quantity",
    unitPrice: "Price per unit (₪)",
    addToPortfolio: "Add to portfolio",
    saveChanges: "Save changes",
    cancelEdit: "Cancel",
    quoteSearching: "Looking up the current price…",
    quoteNotFound: "No asset found for this symbol – you can enter a price manually",
    quoteFailed: "Couldn't fetch a price right now – you can enter it manually",
    loadFailed: "Couldn't load the portfolio from the server. Try refreshing the page.",
    saveFailed: "Saving failed. Please try again.",
    deleteFailed: "Deleting failed. Please try again.",

    myHoldings: "My holdings",
    colAsset: "Asset",
    colType: "Type",
    colQty: "Quantity",
    colPrice: "Price",
    colValue: "Value",
    colShare: "Share",
    colActions: "Actions",
    total: "Total",
    emptyHoldings: "No assets yet. Add your first one above.",
    edit: "Edit",
    delete: "Delete",

    allocationByAsset: "Asset allocation",
    allocationByType: "Type allocation",
    chartView: "Chart view",
    byAsset: "By asset",
    byType: "By type",
    compare: "Compare",
    donutAria: "Portfolio allocation chart",
    portfolioValue: "Portfolio value",
    other: "Other",

    comparePerformance: "Compare",
    timeRange: "Time range",
    range1mo: "1 month",
    range6mo: "6 months",
    range1y: "1 year",
    range5y: "5 years",
    compareAria: "Returns comparison chart",
    yourPortfolio: "Your portfolio",
    portfolioShort: "Portfolio",
    compareEmpty: "Your portfolio is empty – add assets to compare performance.",
    compareLoading: "Loading historical prices…",
    compareFailed: "Couldn't load historical data right now. Please try again in a moment.",
    rangeSentence: { "1mo": "Over the last month", "6mo": "Over the last 6 months", "1y": "Over the last year", "5y": "Over the last 5 years" },
    verdictMore: (k, v) => `more than ${k} (${v})`,
    verdictLess: (k, v) => `less than ${k} (${v})`,
    verdictSame: (k, v) => `the same as ${k} (${v})`,
    compareSummary: (range, mine, a, b) => `${range}, your portfolio returned <strong>${mine}</strong> – ${a} and ${b}.`,
    compareNote: (amount) =>
      `This comparison assumes the current portfolio was held for the whole period, and that the same amount (${amount}) was invested entirely in SPY or QQQM. Includes dividends and the dollar exchange rate, in ILS.`,
    compareFlat: (list) => ` Assets without price history were kept at a constant value: ${list}.`,

    analyst: "The Analyst",
    analystIntro: "Ask a question about your portfolio. Your portfolio data is attached automatically.",
    chip1: "How is my portfolio doing, and what would you recommend?",
    chip2: "How can I improve diversification?",
    chip3: "Is my portfolio too risky?",
    yourQuestion: "Your question",
    questionPlaceholder: "e.g. I'm 30 and investing for the long term – what should I change?",
    ask: "Ask the Analyst",
    clearChat: "Clear conversation",
    disclaimer: "This analysis is generated by AI for educational purposes only and is not investment advice.",
    youAsked: "You asked:",
    generalAnalysis: "General portfolio analysis",
    analyzing: "The analyst is reviewing your portfolio",
    historyLine: (max, n) => `Conversation saved · the analyst remembers up to ${max} recent exchanges (currently: ${n})`,
    confirmClear: "Delete the entire conversation with the analyst?",
    clearFailed: "Couldn't delete the conversation. Please try again.",
    analystEmpty: "Your portfolio is empty – add assets so the analyst can review it.",
    analystGeneric: "Something went wrong while contacting the analyst. Please try again.",
    analystErrors: {
      no_api_key: "The analyst isn't connected yet: add a Google Gemini API key to the .env file and restart the server.",
      bad_api_key: "The API key is invalid. Check the .env file.",
      rate_limited: "Too many requests right now. Please try again in a minute.",
      timeout: "The AI service is busy and didn't respond in time. Please try again in a few minutes.",
      refused: "The analyst can't answer this question. Try rephrasing it.",
    },
  },
};

// Asset types are stored in Hebrew (the database values); only their display label is translated.
const TYPE_LABELS = {
  "מניות": { he: "מניות", en: "Stocks" },
  'אג"ח': { he: 'אג"ח', en: "Bonds" },
  "קרן סל": { he: "קרן סל", en: "ETF" },
  "קרן נאמנות": { he: "קרן נאמנות", en: "Mutual fund" },
  "קריפטו": { he: "קריפטו", en: "Crypto" },
  "מזומן": { he: "מזומן", en: "Cash" },
  "אחר": { he: "אחר", en: "Other" },
};

function loadLang() {
  try {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    if (saved in LANGS) return saved;
  } catch {}
  return "he";
}

let currentLang = loadLang();

// Looks up a translation; function entries are called with the given arguments.
function t(key, ...args) {
  const value = I18N[currentLang][key] ?? I18N.he[key] ?? key;
  return typeof value === "function" ? value(...args) : value;
}

const locale = () => LANGS[currentLang].locale;
const typeLabel = (type) => TYPE_LABELS[type]?.[currentLang] ?? type;

// Cash holdings have free-text names, usually in Hebrew. In English they are shown with
// a matching English name; the stored name never changes.
const CASH_NAMES_EN = {
  'עו"ש': "ILS cash",
  "עו״ש": "ILS cash",
  "עובר ושב": "ILS cash",
  "מזומן": "ILS cash",
  "פיקדון": "ILS deposit",
  "פקדון": "ILS deposit",
  "חיסכון": "ILS savings",
  "חסכון": "ILS savings",
};
const HEBREW = /[\u0590-\u05FF]/;

// Display name of a holding in the current language
function holdingName(name, type) {
  if (currentLang !== "en" || type !== "מזומן" || !HEBREW.test(name)) return name;
  return CASH_NAMES_EN[name.trim()] ?? "ILS cash";
}

// Applies the language to the static page: direction, title and every data-i18n element.
function applyStaticTranslations() {
  const root = document.documentElement;
  root.lang = currentLang;
  root.dir = LANGS[currentLang].dir;
  document.title = t("pageTitle");
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
  // Asset-type options keep their stored (Hebrew) value and show a translated label
  document.querySelectorAll("#type option").forEach((opt) => { opt.textContent = typeLabel(opt.value); });
  document.querySelectorAll(".lang-switch button").forEach((btn) => {
    btn.setAttribute("aria-pressed", btn.dataset.lang === currentLang);
  });
}

function setLang(lang) {
  if (!(lang in LANGS) || lang === currentLang) return;
  currentLang = lang;
  try { localStorage.setItem(LANG_STORAGE_KEY, lang); } catch {}
  applyStaticTranslations();
  document.dispatchEvent(new CustomEvent("langchange"));
}
