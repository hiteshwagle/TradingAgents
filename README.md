<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>
<br>
<div align="center">
  <a href="https://github.com/TauricResearch" target="_blank"><img alt="TradingAgents #1 Repository of the Day" src="https://trendshift.io/api/badge/repositories/16192" width="250" height="55"/></a>
</div>
<br>
<div align="center">
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=de">Deutsch</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=es">Español</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=fr">français</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ja">日本語</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ko">한국어</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=pt">Português</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ru">Русский</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=zh">中文</a>
</div>

---

# TradingAgents: Multi-Agents LLM Financial Trading Framework

## News

<!-- news:start -->
- [2026-09] **TradingAgents v0.5.1** released with a package layout organised by what each module holds (import paths moved), optional Jev screening of social posts, GPT-6 Sol and Luna as the default models, and fixes to run isolation and SEC EDGAR statements.
- [2026-09] **TradingAgents v0.5.0** released with point-in-time integrity across every dated path, SEC EDGAR fundamentals served as filed, backtesting over a ticker and date grid, portfolio-aware runs, and current model lineups across every provider.
- [2026-08] **TradingAgents v0.4.0** released with look-ahead / point-in-time fixes across FRED macro, social sentiment, and the decision-log memory; clearer decision signals; working CLI checkpoint resume; Trader price grounding; and the GPT-5.6 and GLM-5.3 models.

Full release notes are in [CHANGELOG.md](CHANGELOG.md).

<details>
<summary>Earlier news</summary>

- [2026-07] **TradingAgents v0.3.1** released with correctness and stability fixes: Alpha Vantage look-ahead filtering, graph-router crash-safety, graph-shape-aware checkpoint resume, working crypto sentiment sources, a configurable LLM retry budget, Bedrock API-key auth, and Claude Sonnet 5 / Fable 5 support.
- [2026-06] **TradingAgents v0.3.0** released with a verified data-access contract, an expanded provider registry (NVIDIA, Kimi, Groq, Mistral, Bedrock, and any OpenAI-compatible endpoint), FRED and Polymarket data vendors, a current-generation model catalog, and a CI gate.
- [2026-05] **TradingAgents v0.2.5** released with the grounded Sentiment Analyst, GPT-5.5 etc. model coverage, Qwen/GLM/MiniMax dual-region support, `TRADINGAGENTS_*` env-var configurability with API-key auto-detection, remote Ollama support, non-US alpha benchmarks, and ticker path-traversal hardening.
- [2026-04] **TradingAgents v0.2.4** released with structured-output agents (Research Manager, Trader, Portfolio Manager), LangGraph checkpoint resume, persistent decision log, DeepSeek/Qwen/GLM/Azure provider support, Docker, and a Windows UTF-8 encoding fix.
- [2026-03] **TradingAgents v0.2.3** released with multi-language support, GPT-5.4 family models, unified model catalog, backtesting date fidelity, and proxy support.
- [2026-03] **TradingAgents v0.2.2** released with GPT-5.4/Gemini 3.1/Claude 4.6 model coverage, five-tier rating scale, OpenAI Responses API, Anthropic effort control, and cross-platform stability.
- [2026-02] **TradingAgents v0.2.0** released with multi-provider LLM support (GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x) and improved system architecture.
- [2026-01] **Trading-R1** [Technical Report](https://arxiv.org/abs/2509.11420) released, with [Terminal](https://github.com/TauricResearch/Trading-R1) expected to land soon.

</details>
<!-- news:end -->

<div align="center">

🚀 [TradingAgents](#tradingagents-framework) | ⚡ [Installation & CLI](#installation-and-cli) | 🎬 [Demo](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [Package Usage](#tradingagents-package) | 🤝 [Contributing](#contributing) | 📄 [Citation](#citation)

</div>

> 🎉 **TradingAgents** officially released! We have received numerous inquiries about the work, and we would like to express our thanks for the enthusiasm in our community.
>
> So we decided to fully open-source the framework. Looking forward to building impactful projects with you!

## TradingAgents Framework

TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms. By deploying specialized LLM-powered agents: from fundamental analysts, sentiment experts, and technical analysts, to trader, risk management team, the platform collaboratively evaluates market conditions and informs trading decisions. Moreover, these agents engage in dynamic discussions to pinpoint the optimal strategy.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents framework is designed for research purposes. Trading performance may vary based on many factors, including the chosen backbone language models, model temperature, trading periods, the quality of data, and other non-deterministic factors. [It is not intended as financial, investment, or trading advice.](https://tauric.ai/disclaimer/)

Our framework decomposes complex trading tasks into specialized roles.

### Analyst Team
- Fundamentals Analyst: Evaluates company financials and performance metrics, identifying intrinsic values and potential red flags.
- Sentiment Analyst: Aggregates news headlines, StockTwits, X Posts, and Reddit chatter into a single sentiment read to gauge short-term market mood.
- News Analyst: Monitors company, sector, global-market, and geopolitical news, interpreting confirmed catalysts and risks.
- Macro Analyst: Separately evaluates rates, inflation, growth, liquidity, Treasury yields, global macro news, forward-looking event probabilities, and upcoming FRED economic-release dates for stocks and crypto. Release dates are event-risk context rather than directional signals; historical runs withhold the live calendar, and FOMC meetings still require the Federal Reserve's official calendar.
- Technical Analyst: Utilizes technical indicators (like MACD and RSI) to detect trading patterns and forecast price movements.

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Researcher Team
- Comprises both bullish and bearish researchers who critically assess the insights provided by the Analyst Team. Through structured debates, they balance potential gains against inherent risks.

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Trader Agent
- Composes reports from the analysts and researchers to make informed trading decisions, determining the timing and magnitude of trades.

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Risk Management and Portfolio Manager
- Continuously evaluates portfolio risk by assessing market volatility, liquidity, and other risk factors. The risk management team evaluates and adjusts trading strategies, providing assessment reports to the Portfolio Manager for final decision.
- The Portfolio Manager approves/rejects the transaction proposal. If approved, the order will be sent to the simulated exchange and executed.

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## Installation and CLI

### Installation

Clone TradingAgents:
```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
```

Create a virtual environment in any of your favorite environment managers:
```bash
conda create -n tradingagents python=3.12
conda activate tradingagents
```

Or with [uv](https://docs.astral.sh/uv/):
```bash
uv venv --python 3.12
source .venv/bin/activate
```

Install the package and its dependencies (`uv pip install .` with uv):
```bash
pip install .
```

### Docker

Alternatively, run with Docker:
```bash
cp .env.example .env  # add your API keys
docker compose run --rm tradingagents
```

After updating the repository, rebuild the image with `docker compose build`.

For local models with Ollama:
```bash
docker compose --profile ollama run --rm tradingagents-ollama
```

### Required APIs

TradingAgents supports multiple LLM providers. Set the API key for your chosen provider:

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export XAI_API_KEY=...             # xAI (Grok)
export DEEPSEEK_API_KEY=...        # DeepSeek
export DASHSCOPE_API_KEY=...       # Qwen — International (dashscope-intl.aliyuncs.com)
export DASHSCOPE_CN_API_KEY=...    # Qwen — China (dashscope.aliyuncs.com)
export ZHIPU_API_KEY=...           # GLM via Z.AI (international)
export ZHIPU_CN_API_KEY=...        # GLM via BigModel (China, open.bigmodel.cn)
export MINIMAX_API_KEY=...         # MiniMax — Global (api.minimax.io)
export MINIMAX_CN_API_KEY=...      # MiniMax — China (api.minimaxi.com)
export OPENROUTER_API_KEY=...      # OpenRouter
export MISTRAL_API_KEY=...         # Mistral
export MOONSHOT_API_KEY=...        # Kimi (Moonshot)
export GROQ_API_KEY=...            # Groq
export NVIDIA_API_KEY=...          # NVIDIA NIM
export FRED_API_KEY=...            # FRED macro data (free, optional)
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage
export APCA_API_KEY_ID=...         # Alpaca Market Data news (optional)
export APCA_API_SECRET_KEY=...     # Alpaca Market Data news (optional)
export FINNHUB_API_KEY=...         # Finnhub shared data enrichment (optional)
export X_BEARER_TOKEN=...          # X recent-Post search (optional, usage-billed by X)
export STOCKTWITS_USERNAME=...     # Authorized StockTwits Firestream account (optional)
export STOCKTWITS_PASSWORD=...     # Authorized StockTwits Firestream account (optional)
export TYPESAFE_API_KEY=...        # Jev social-post screening (optional)
```

For Azure OpenAI, copy `.env.enterprise.example` to `.env.enterprise` and fill
in your credentials. Use `llm_provider: "azure_responses"` for models such as
GPT-6.1 Sol that require the Responses API for tool calling. This dedicated
adapter sets `use_responses_api=True`, disables server-side response storage,
and accepts `AZURE_OPENAI_API_VERSION` (with `OPENAI_API_VERSION` as a legacy
fallback). Keep `AZURE_OPENAI_ENDPOINT` at the resource root, for example
`https://your-resource.openai.azure.com/`, rather than the full
`/openai/responses` request URL. The original `azure` provider remains available
for existing Chat Completions deployments.

For AWS Bedrock, install the extra with `pip install ".[bedrock]"`, set `llm_provider: "bedrock"`, configure AWS credentials (environment variables, `~/.aws/credentials`, or an IAM role) and `AWS_DEFAULT_REGION`, and use a Bedrock model ID, e.g. `us.anthropic.claude-opus-4-8-v1:0`.

For local models, configure Ollama with `llm_provider: "ollama"`. The default endpoint is `http://localhost:11434/v1`; set `OLLAMA_BASE_URL` to point at a remote `ollama-serve`. Pull models with `ollama pull <name>`, and pick "Custom model ID" in the CLI for any model not listed by default.

For any other OpenAI-compatible server (vLLM, LM Studio, llama.cpp, or a custom relay), use `llm_provider: "openai_compatible"` and set the endpoint via `backend_url` (or `TRADINGAGENTS_LLM_BACKEND_URL`), e.g. `http://localhost:8000/v1` for vLLM or `http://localhost:1234/v1` for LM Studio. The model is whatever your server serves. No key is needed for local servers; set `OPENAI_COMPATIBLE_API_KEY` when the endpoint requires one.

With `X_BEARER_TOKEN` set, the Sentiment Analyst adds recent X Posts matching the ticker/company and market-event terms (earnings, revenue, guidance, acquisitions, partnerships, SEC activity, upgrades, and downgrades). The client follows X's current recent-search contract (`post.fields`, with `author_id` requested as an expansion) and orders Posts by `likes + 2×reposts + replies` using X's `repost_count` metric. It also accepts the former `retweet_count` name in existing cache files. HTTPS requests use `requests` with the CA bundle supplied explicitly by `certifi`. That score measures attention, not sentiment or credibility. Set `X_POST_LIMIT_PER_SYMBOL` (default `20`) and `X_CACHE_TTL_SECONDS` (default `86400`) to control usage. The recent-search endpoint is for live/recent analysis and may not cover an older backtest date. Without the token, the X source is marked unavailable and the run continues. API failures include a sanitized status/reason in the report and terminal log; the bearer token is redacted.

API callers may set `options.x_posts_mode` to `disabled`, `recent`, or
`cache_only`. `disabled` makes no X request, `cache_only` accepts only an exact
local cached response, and `recent` automatically skips historical windows older
than seven days instead of spending quota on an unsupported recent-search call.

StockTwits uses the supported Firestream sentiment-detail endpoint. Set
`STOCKTWITS_USERNAME` and `STOCKTWITS_PASSWORD` only if the account is authorized
for Firestream; the client sends HTTP Basic authentication and returns current
aggregate sentiment, message-volume, buzz, and participation metrics. It does
not use the retired anonymous symbol-stream endpoint. Without credentials the
source is marked unavailable without a network request. Historical runs also
skip StockTwits because this endpoint is current-only, preventing look-ahead
bias.

Query the same packaged client directly as JSON:

```bash
tradingagents-x NVDA --company NVIDIA --limit 20
# From an uninstalled source checkout:
python -m cli.x_posts NVDA --company NVIDIA --limit 20
```

Python callers can import it without adding the parent repository to `PYTHONPATH`:

```python
from tradingagents.dataflows.vendors.x_posts import search_symbol_posts

result = search_symbol_posts("NVDA", "NVIDIA", limit=20)
posts = result["posts"]
```

With `TYPESAFE_API_KEY` set, the Sentiment Analyst screens X and Reddit posts with TypeSafe's Jev before reading them. Posts that are not about the company are dropped, and each source opens with a count of the remaining posts by stance: bullish, bearish, neutral, or unclear. StockTwits supplies aggregates rather than individual posts, so it is not sent to Jev. Without the key, posts pass through unscreened. `jev-latest` moves with new releases; set `TYPESAFE_DEFAULT_MODEL` to a versioned ID such as `jev-1.13.0` to hold it fixed across runs.

Alpaca Market Data, Yahoo Finance, and Finnhub are enabled for symbol-specific
news used by the News and Sentiment Analysts. Set `APCA_API_KEY_ID` and
`APCA_API_SECRET_KEY` (`ALPACA_API_KEY` and `ALPACA_SECRET_KEY` are accepted
aliases), and set `FINNHUB_API_KEY` to include Finnhub. The default configuration is:

```python
from copy import deepcopy

from tradingagents.default_config import DEFAULT_CONFIG

config = deepcopy(DEFAULT_CONFIG)
config["tool_vendors"]["get_news"] = "alpaca,yfinance,finnhub"
config["tool_vendor_modes"]["get_news"] = "aggregate"
```

Aggregate mode calls every configured provider and labels each result so the
agent can use the combined coverage. If Alpaca or Finnhub is not configured,
throttled, unavailable, or has no usable articles, Yahoo Finance still supplies news. Alpaca results come
from its historical News API (currently supplied by Benzinga), include article
content when available, and are defensively filtered by both creation and update
timestamps so a past analysis cannot read a later article revision. Alpaca is
never used for global news or insider transactions.

Finnhub is a shared vendor rather than a separate client in every agent. News
and Sentiment receive company news; News and Macro receive current general,
forex, crypto, and merger news; Fundamentals receives company profile, peers,
metrics, earnings, recommendation, filing-adjacent, and insider evidence; and
Market can use live US quote and exchange-session context. Research, Risk, and
Trader consume the analyst reports and do not repeat those API calls. Responses
share a disk cache under `TRADINGAGENTS_CACHE_DIR/finnhub`, per-key
single-flight locks, a process-wide rate limiter, a per-run request budget, and
bounded concurrency. Cache hits do not consume the per-run budget.

Set the per-minute allowance to the value displayed in your Finnhub dashboard:

```env
FINNHUB_API_KEY=...
FINNHUB_REQUESTS_PER_MINUTE=30
FINNHUB_MAX_CALLS_PER_RUN=30
FINNHUB_MAX_CONCURRENCY=2
FINNHUB_CACHE_TTL_SECONDS=900
FINNHUB_HISTORICAL_CACHE_TTL_SECONDS=86400
```

The defaults of 30 requests/minute and 30 uncached requests per TradingAgents
run are deliberately conservative. When the run budget is exhausted, Finnhub
stops and the configured vendor chain continues with other providers. Live
quotes, exchange state, current metrics/profile, latest market news, and event-calendar
snapshots are withheld from historical runs. Dated company news, earnings,
recommendations, and insider rows are filtered at the analysis cutoff. Finnhub
is optional: another configured vendor can still serve the run when its key is
missing, its free entitlement excludes an endpoint, or it is throttled.

Project-owned HTTPS requests—including StockTwits, Reddit, X, FRED, SEC EDGAR,
Polymarket, Alpaca, Finnhub, and Jev—use `requests` with certificate
verification enabled against Certifi's current CA bundle. This avoids relying on
an incomplete operating-system or Python `urllib` trust store; TLS verification
is never disabled.

Alternatively, copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### CLI Usage

Launch the interactive CLI:
```bash
tradingagents          # installed command
python -m cli.main     # alternative: run directly from source
```
You will see a screen where you can select your desired tickers, analysis date, LLM provider, research depth, and more. Your previous run's answers come back as the defaults, so pressing Enter accepts them. The `TRADINGAGENTS_*` variables in `.env` still skip their step entirely.

### Markets and tickers

TradingAgents works with any market Yahoo Finance covers, using the exchange-suffixed ticker. Company identity and the alpha benchmark resolve automatically per market.

- US: `AAPL`, `SPY`
- Hong Kong: `0700.HK` · Tokyo: `7203.T` · London: `AZN.L`
- India: `RELIANCE.NS`, `.BO` · Canada: `.TO` · Australia: `.AX`
- China A-shares: Shanghai `.SS`, Shenzhen `.SZ` (e.g. `600519.SS` for Kweichow Moutai)
- Crypto: `BTC-USD`, `ETH-USD`

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

An interface will appear showing results as they load, letting you track the agent's progress as it runs.

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## TradingAgents Package

### Implementation Details

We built TradingAgents with LangGraph to ensure flexibility and modularity. The framework supports multiple LLM providers: OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen (Alibaba DashScope, international and China endpoints), GLM (Zhipu), MiniMax (global + China), OpenRouter, Ollama for local models, and Azure OpenAI for enterprise.

### Python Usage

To use TradingAgents inside your code, you can import the `tradingagents` module and initialize a `TradingAgentsGraph()` object. The `.propagate()` function will return a decision. You can run `main.py`, here's also a quick example:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# forward propagate
_, decision = ta.propagate("NVDA", "2026-09-01")
print(decision)
```

You can also adjust the default configuration to set your own choice of LLMs, debate rounds, etc.

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # e.g. openai, google, anthropic, deepseek, groq, ollama; openai_compatible covers any OpenAI-compatible endpoint (vLLM, LM Studio, llama.cpp, ...)
config["deep_think_llm"] = "gpt-6-sol"    # Model for complex reasoning
config["quick_think_llm"] = "gpt-6-luna"   # Model for quick tasks
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-09-01")
print(decision)
```

See `tradingagents/default_config.py` for all configuration options.

### Local HTTP API

Install the API extra and start the service:

```bash
pip install -e ".[api]"
export TRADINGAGENTS_API_KEY="replace-with-a-strong-local-key"
tradingagents-api
```

The server binds to `127.0.0.1:8000` by default. Interactive OpenAPI documentation
is available at `http://127.0.0.1:8000/docs`. Keep the loopback binding unless a
trusted reverse proxy provides TLS and network access control. The API key is
optional on loopback; startup rejects a non-loopback host when no key is configured.
The command loads the repository's `.env` file automatically.

Start an asynchronous stock study:

```bash
curl -X POST http://127.0.0.1:8000/v1/analyses \
  -H "Authorization: Bearer $TRADINGAGENTS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "trade_date": "2026-09-01",
    "asset_type": "stock",
    "analysts": ["market", "social", "news", "fundamentals", "macro"],
    "options": {"max_debate_rounds": 1, "max_risk_rounds": 1}
  }'
```

The response contains an `analysis_id`. Poll
`GET /v1/analyses/{analysis_id}` until its status is `completed`; the result is
JSON with the final rating, trader entry/stop fields, reports (including the
dedicated `reports.macro` output when selected), debates, and source
URLs. Debate output includes the combined histories and the individual bull,
bear, aggressive, conservative, and neutral histories. `GET
/v1/analyses/{analysis_id}/events` returns job progress and
`POST /v1/analyses/{analysis_id}/cancel` requests cancellation. Other discovery
endpoints are `GET /v1/health` and `GET /v1/capabilities`.

The API performs analysis only and never sends broker orders. LLM/data credentials,
provider endpoints, and output paths remain server-side. Jobs use process memory by
default; configure the SQLite journal below to retain terminal status across restarts.
Generated reports and normal TradingAgents logs remain on disk. One worker is the safe default because
each analysis is resource-intensive; tune `TRADINGAGENTS_API_WORKERS` only after
validating provider rate limits and storage concurrency.

Set `TRADINGAGENTS_API_DB_PATH` to retain completed/failed job status and events
across API restarts. A job that was queued or running during a restart is recorded
as failed with `server_restarted`; it is never silently resumed with an uncertain
graph state. The Docker API service stores this journal with reports, cache and
decision memory on the `tradingagents_data` volume:

```bash
docker compose up -d api
```

### Alpaca activity scanner

The live US-stock scanner combines Alpaca movers, most-active-by-volume,
most-active-by-trades and recent news, then enriches the bounded union with batch
snapshots and historical bars. It applies transparent liquidity checks and a
deterministic movement/RVOL/activity/news score. It retains gainers and losers;
the score is attention-worthiness, not a trade recommendation.

```bash
python -m tradingagents.scanner --top 20 --feed iex
```

The same result is available to authenticated callers at `POST /v1/scanner/scan`
with JSON such as `{"top_n": 20, "feed": "iex"}`. The result includes timestamps,
session, feed, score components, completeness, excluded candidates and failed
optional sources. When SIP screener activity is combined with IEX snapshot/bar
volume, candidates carry a comparability warning. Historical scan dates are
rejected because today's mover and activity lists cannot reconstruct past rankings.
Outside regular hours, rankings are explicitly labeled as potentially belonging to
the prior session. Multi-symbol news tags are discovery metadata and are not treated
as evidence that a story is equally material to every tagged company.
The scanner never invokes an LLM or submits an order.

### Fundamentals as filed

US company statements can come from SEC EDGAR, which records the date every figure was filed. A run dated in the past then reads the statements exactly as they stood that day: a fiscal year that has ended but has not been filed yet is not served, and a figure restated later still reads as first reported. Apple's 2008 total assets were filed as $39.6B and restated to $36.2B in 2010, so a run dated in between reads $39.6B.

EDGAR needs no account or API key. Add the vendor to the chain:

```python
config["data_vendors"]["fundamental_data"] = "sec_edgar,yfinance"
```

SEC asks callers to identify themselves and refuses requests that carry no contact address, so a default one is sent. Set your own so SEC can reach you rather than the project:

```bash
SEC_EDGAR_USER_AGENT="Your Name your@email.com"
```

It covers companies that file with the SEC, including foreign companies listed in the US. Anything else, such as Hong Kong or A-share listings, falls through to the next vendor in the chain. EDGAR's machine-readable filings begin in 2009, and a fourth quarter is reported as unavailable rather than derived, because filers publish it only inside the annual figure.

### Current holdings

By default the agents do not know what you hold, so their guidance is written for a reader who applies it to their own position. Pass a portfolio to have the trader, the risk analysts and the portfolio manager work against your actual book.

```python
from tradingagents.portfolio import PortfolioContext

portfolio = PortfolioContext.model_validate({
    "cash": 25000.0,
    "currency": "USD",
    "positions": [{"ticker": "NVDA", "quantity": 120, "average_price": 150.0}],
})
_, decision = ta.propagate("NVDA", "2026-09-01", portfolio=portfolio)
```

The CLI takes the same content as a JSON file: `tradingagents --portfolio my_book.json`.

An empty `positions` list means a flat book, which is different from passing nothing. A run without a portfolio is never treated as flat.

## Persistence and Recovery

TradingAgents persists two kinds of state across runs.

### Decision log

The decision log is always on. Each completed run appends its decision to `~/.tradingagents/memory/trading_memory.md`. On the next run for the same ticker, TradingAgents fetches the realised return (raw, and alpha against the instrument's regional benchmark), generates a one-paragraph reflection, and injects the most recent same-ticker decisions plus recent cross-ticker lessons into the Portfolio Manager prompt, so each analysis carries forward what worked and what didn't.

Override the path with `TRADINGAGENTS_MEMORY_LOG_PATH`.

### Checkpoint resume

Checkpoint resume is opt-in via `--checkpoint`. When enabled, LangGraph saves state after each node so a crashed or interrupted run resumes from the last successful step instead of starting over. The run view says whether it resumed a saved run or started fresh. Checkpoints are cleared automatically on successful completion.

Per-ticker SQLite databases live at `~/.tradingagents/cache/checkpoints/<TICKER>.db` (override the base with `TRADINGAGENTS_CACHE_DIR`). Use `--clear-checkpoints` to reset all of them before a run.

```bash
tradingagents --checkpoint           # enable for this run
tradingagents --clear-checkpoints    # reset before running
```

```python
config = DEFAULT_CONFIG.copy()
config["checkpoint_enabled"] = True
ta = TradingAgentsGraph(config=config)
_, decision = ta.propagate("NVDA", "2026-09-01")
```

## Evaluating decisions over time

One run gives one decision, which cannot tell you whether the system decides well. `run_backtest` runs the same pipeline over a grid of tickers and dates, writes to a decision log of its own, and scores the decisions whose holding window has since traded.

```python
from tradingagents.backtest import iter_grid, run_backtest, summarize

dates = iter_grid("2026-06-01", "2026-08-01", every_n_days=7)
result = run_backtest(["NVDA", "AAPL"], dates, config, selected_analysts=["market", "news"])
print(summarize(result).render())
```

From the CLI:

```bash
tradingagents backtest NVDA,AAPL --start 2026-06-01 --end 2026-08-01 --every 7
```

Each cell is scored on realized alpha against the instrument's regional benchmark, grouped by rating. Your own decision log is never written to, and re-running the same grid with `run_id=result.run_id` skips the cells that already ran, so an interrupted sweep continues where it stopped.

## Reproducibility

TradingAgents is LLM-driven, so two runs of the same ticker and date can differ. This is expected for a research tool built on language models, not a defect. The variation comes from a few distinct sources, and it helps to separate them.

Language model sampling is non-deterministic. Even at a fixed temperature, providers do not guarantee byte-identical output across calls, and reasoning models (the default GPT-6 family, and any thinking-mode model) vary the most because their internal reasoning is itself sampled.

Live data moves. Current-date StockTwits aggregates and recent social/news data
can change between runs. Historical runs skip current-only StockTwits data and
each remaining vendor enforces its own point-in-time coverage; an unavailable
marker is safer than substituting present-day data for a past date.

To reduce variation you can lower the sampling temperature. Set `temperature` in your config (or `TRADINGAGENTS_TEMPERATURE` in `.env`); lower values make models that honor it more repeatable. The current curated models are reasoning-first and largely ignore temperature, so for tighter reproducibility name a non-reasoning model in your config, or in `TRADINGAGENTS_DEEP_THINK_LLM` and `TRADINGAGENTS_QUICK_THINK_LLM`. Any model ID your provider serves is accepted, whether or not the picker lists it.

```python
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["temperature"] = 0.0
# Reasoning models ignore temperature. For tighter reproducibility, name a
# non-reasoning model in deep_think_llm / quick_think_llm.
```

What does not vary anymore: the analyzed company identity is resolved deterministically from the ticker before any agent runs, and the market analyst grounds exact price and indicator claims in a verified data snapshot. Earlier reports of "different companies" or fabricated price levels across runs are addressed by these two mechanisms.

Backtest results are not guaranteed to match any published figure. Returns depend on the model, the temperature, the date range, data quality, and the sampling above. Treat the framework as a research scaffold for studying multi-agent analysis, not as a strategy with a fixed, replicable return.

## Contributing

Contributions are welcome: bug fixes, documentation, and feature ideas; past contributions are credited per release in [`CHANGELOG.md`](CHANGELOG.md).

## Citation

Please reference our work if you find *TradingAgents* provides you with some help :)

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```
