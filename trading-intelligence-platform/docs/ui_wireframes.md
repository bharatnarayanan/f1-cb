# Trading Intelligence Platform — UI Wireframes

Style direction (from `docs/buildspec.json` → `ui.style_direction`):
dark-first, data-dense trading-terminal aesthetic. Monospace for
prices/indicators. Green/red reserved strictly for bullish/bearish
direction and P&L. The reasoning tree is collapsed by default — this is a
decision-support tool, not a black box, but it shouldn't overwhelm the
scan-and-decide flow either.

## Key screens

### 1. Login
```
┌─────────────────────────────────────┐
│   Trading Intelligence Platform      │
│                                       │
│   [ email                        ]   │
│   [ password                     ]   │
│                                       │
│           [ Log in ]                 │
└─────────────────────────────────────┘
```

### 2. Dashboard home
```
┌───────────────────────────────────────────────────────────────────┐
│ TIP   Tactical  Impulse  Strategic  BTST   Marketplace   Journal  │
├───────────────────────────────────────────────────────────────────┤
│ India VIX: 14.2 (Normal)     Mode: ● Live-manual  ○ Paper          │
│ Horizon: [ 15m ] [ 30m ] [ 1h ] [ 2h ]                              │
├───────────────────────────────────────────────────────────────────┤
│ TACTICAL — 15m                                                      │
│ ┌─────────────────────────────────────────────────────────────┐   │
│ │ NIFTY 24800 CE   BUY_CE   Confidence 78  Risk 32  Conv 71     │   │
│ │ Entry 245  SL 228  Target 268           [ View reasoning ▾ ]  │   │
│ ├─────────────────────────────────────────────────────────────┤   │
│ │ BANKNIFTY 52300 PE  BUY_PE  Confidence 61  Risk 44  Conv 55   │   │
│ │ Entry 310  SL 288  Target 350           [ View reasoning ▾ ]  │   │
│ └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
│ IMPULSE (institutional-flow watch)                                   │
│ ┌─────────────────────────────────────────────────────────────┐   │
│ │ RELIANCE — basket-order-style OI+volume spike at 14:32         │   │
│ │ NIFTY follow-through likely           [ View reasoning ▾ ]     │   │
│ └─────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

### 3. Recommendation deep-dive (reasoning tree)
```
┌───────────────────────────────────────────────────────────────────┐
│ NIFTY 24800 CE — Tactical — 15m horizon             [ Dismiss ]    │
├───────────────────────────────────────────────────────────────────┤
│ Confidence 78  |  Risk 32  |  Conviction 71  |  VIX regime: Normal  │
│                                                                       │
│ ▾ Macro bias (weight 0.25) — score 0.82                              │
│     Weekly/Daily/1h support at 24,650 held on 3 tests; bullish bias │
│ ▾ Pattern + negation (weight 0.20) — score 0.75                     │
│     5m bullish Engulfing at 13:55; predicted negation window        │
│     3-6 candles (~15-30 min), heuristic-v1, VIX-normal regime       │
│ ▾ Heavyweight/sector alignment (weight 0.25) — score 0.80            │
│     RELIANCE, HDFC BANK, ICICI BANK confirm bullish 5m pattern;      │
│     NIFTY BANK sector index aligned                                  │
│ ▾ OI accumulation (weight 0.15) — score 0.70                        │
│     24800 CE OI +18% in last 30 min, delta 0.54                     │
│ ▾ RSI alignment (weight 0.15) — score 0.68                          │
│     NIFTY 5m RSI 61, rising, not yet overbought                     │
│                                                                       │
│ Entry 245  Stop 228 (below 50MA)  Target 268 (prior red-candle high) │
└───────────────────────────────────────────────────────────────────┘
```

### 4. Watchlist & risk settings
```
┌───────────────────────────────────────────────────────────────────┐
│ Watchlist & Risk Settings                                           │
├───────────────────────────────────────────────────────────────────┤
│ Heavyweight constituents (15)                                       │
│ [x] RELIANCE  [x] HDFCBANK  [x] ICICIBANK  [x] INFY  [x] TCS  ...   │
│ Sector indices                                                       │
│ [x] NIFTY BANK  [x] NIFTY IT  [x] NIFTY FMCG  [x] NIFTY PHARMA       │
│                                                                       │
│ VIX regime thresholds     Normal < [15.0]  Elevated < [20.0]         │
│                           High < [30.0]  Extreme suppresses tactical  │
│ [x] Dampen conviction on expiry days                                 │
│ Max recommendations/day  [ 20 ]                                      │
│                                                                       │
│ Strike-selection rule overrides                                      │
│ RSI entry threshold: [ > 55 ]   OI accumulation min: [ +10% ]        │
└───────────────────────────────────────────────────────────────────┘
```

### 5. Strategy Marketplace
```
┌───────────────────────────────────────────────────────────────────┐
│ Strategy Marketplace                          [ + Submit strategy ] │
├───────────────────────────────────────────────────────────────────┤
│ Name              Source     Status       Confidence   Actions      │
│ BVWR (founder)    user_rule  usable        74           [Backtest]  │
│                                                          [Export▾]   │
│ "3-candle scalp"  video      backtested    58           [Fuse]      │
│ "ORB variant"     text       extracted     —            [Backtest]  │
└───────────────────────────────────────────────────────────────────┘

Submit strategy modal:
┌───────────────────────────────────────────────────────────────────┐
│ Submit Strategy                                        [ Submit ]  │
├───────────────────────────────────────────────────────────────────┤
│ Source: ( ) YouTube URL  ( ) Text  ( ) Pseudocode  ( ) Pine Script  │
│ [ https://youtube.com/watch?v=...                              ]   │
│ Name: [ 3-candle scalp                                         ]   │
└───────────────────────────────────────────────────────────────────┘
```

### 6. Strategy backtest result
```
┌───────────────────────────────────────────────────────────────────┐
│ Backtest — BVWR (2025-04-01 → 2026-06-30)                           │
├───────────────────────────────────────────────────────────────────┤
│ Win rate: 61%   Sharpe: 1.12   Max DD: -11.4%   Return: 34%          │
│                                                                       │
│  Equity curve                                                        │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │            ╱╲      ╱‾‾╲                                      │    │
│  │  ╱‾╲    ╱‾╯  ╲  ╱‾╯    ╲╱‾                                  │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                       │
│ Confidence score: 74/100   [ Export Pine Script ]  [ Export Python ] │
└───────────────────────────────────────────────────────────────────┘
```

### 7. Paper trading
```
┌───────────────────────────────────────────────────────────────────┐
│ Paper Trading                    Mode: ● Paper   ○ Live-manual      │
├───────────────────────────────────────────────────────────────────┤
│ Open simulated positions                                             │
│ NIFTY 24800 CE   Entry 245   Current 258   +5.3% (unrealized)        │
│                                                                       │
│ Simulated equity curve (last 30 days)                                 │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │        ╱╲   ╱╲    ╱‾‾‾‾╲                                     │    │
│  └────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────┘
```

### 8. Trade journal / feedback
```
┌───────────────────────────────────────────────────────────────────┐
│ Trade Journal                                                        │
├───────────────────────────────────────────────────────────────────┤
│ Log outcome for: NIFTY 24800 CE (Tactical, 13:55)                    │
│ Outcome: ( ) Win  ( ) Loss  ( ) Breakeven  ( ) Not taken              │
│ Realized P&L %: [       ]                                            │
│ Observation: [ Negation happened faster than predicted, ~2 candles ] │
│                                                       [ Save entry ]  │
├───────────────────────────────────────────────────────────────────┤
│ History                                                               │
│ 07-08  NIFTY 24800 CE   Win   +8.2%   "Negation faster than predicted"│
│ 07-07  BANKNIFTY 52100 PE  Loss  -4.1%  "VIX spiked mid-trade"        │
└───────────────────────────────────────────────────────────────────┘
```

### 9. Alerts settings
```
┌───────────────────────────────────────────────────────────────────┐
│ Alert Settings                                                       │
├───────────────────────────────────────────────────────────────────┤
│ Telegram bot: [ @tip_alerts_bot linked ✓ ]           [ Relink ]      │
│ Email: [ founder@example.com                    ]                    │
│ Alert on: [x] Tactical  [x] Impulse  [x] Strategic  [x] BTST          │
│                                                       [ Save ]        │
└───────────────────────────────────────────────────────────────────┘
```

## User flows (from `docs/buildspec.json` → `ui.user_flows`)

1. Open dashboard → pick a forecast horizon → scan Tactical cards →
   expand reasoning tree on the top pick → execute manually in Zerodha's
   own app → log the outcome later in the trade journal.
2. Receive a Telegram alert on a fired Impulse recommendation → open
   dashboard deep-dive → decide to act or skip.
3. Submit a YouTube strategy video → Strategy Agent extracts logic →
   review extracted rule set → run independent backtest → fuse with an
   existing rule set or keep standalone → export Pine Script.
4. Toggle Paper mode → let recommendations auto-fill as simulated trades
   → review simulated P&L before trusting a new rule set live-manual.
5. On an expiry day, see Tactical recommendations flagged low-conviction
   with a warning banner, alongside a BTST suggestion if the pattern
   supports it.
