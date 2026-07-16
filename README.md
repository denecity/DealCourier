# DealCourier

Automatically scrapes the Swiss marketplaces **tutti.ch**, **ricardo.ch** and **anibis.ch** for items you want, uses an AI model to estimate each listing's fair market value, filters by your rules, and pings you on Discord the moment a good deal appears — so you can be the first to react.

The interface is a self-hosted web dashboard (no cloud, no phone app). You run it on your own machine and open it in a browser.

```
2024 Denis Titov  ·  dtitov@ethz.ch
```

---

## Table of contents
1. [How it works](#how-it-works)
2. [Prerequisites](#prerequisites)
3. [Initial startup (for users)](#initial-startup-for-users)
4. [Configuration reference](#configuration-reference)
5. [Setting up a product search](#setting-up-a-product-search)
6. [The dashboard tabs](#the-dashboard-tabs)
7. [Notifications](#notifications)
8. [Troubleshooting](#troubleshooting)

---

## How it works

1. You describe what you're hunting for as a **Search Item** in the web UI (e.g. "RTX 4060").
2. On a schedule, DealCourier asks the AI to generate dozens of **search-term variations** (brand names, misspellings, German/English, colloquial terms).
3. It scrapes the enabled marketplaces with those terms and stores every new listing in a local SQLite database.
4. Each new listing is sent to the AI, which returns an estimated fair value (CHF), a confidence score, detected included components, and the result of any custom filters you defined.
5. Listings that pass your price / profit / value-factor / custom-filter thresholds are marked **passed**.
6. Passed listings trigger a **Discord webhook** notification (if configured) with price, estimated value, profit, value factor, distance from Zurich and a link.

Everything runs locally. The only thing that leaves your machine is the listing text sent to your AI provider for valuation, and the Discord webhook call.

---

## Prerequisites

- **Python 3.11 or newer.** Check with `python --version` (Windows) / `python3 --version` (macOS).
- An **AI API key** from any OpenAI-compatible provider. DealCourier does not care which vendor — see [Configuration reference](#configuration-reference). The defaults assume [OpenRouter](https://openrouter.ai) because one key gives you access to hundreds of models (including free ones).
- *(Optional)* a **Discord webhook URL** for push notifications.

> Recommended (not required): [`uv`](https://docs.astral.sh/uv/) — a fast Python package manager that creates the virtualenv and installs dependencies for you. The startup scripts use it if present, otherwise they fall back to plain `pip`.

---

## Initial startup (for users)

These steps assume you cloned the repo and are in the project folder.

### 1. Create your config file
A clean template is shipped as **`config_init.yaml`**. Copy it to `config.yaml` and edit it:

```bash
# Windows (PowerShell / cmd)
copy config_init.yaml config.yaml

# macOS / Linux
cp config_init.yaml config.yaml
```

Open `config.yaml` in a text editor and set **at minimum**:

```yaml
api_key: "sk-or-...your key..."     # your AI provider key
base_url: "https://openrouter.ai/api/v1"
default_model: "deepseek-v4-flash"
terms_model: "z-ai/glm-5.2"
```

`config.yaml` is in `.gitignore`, so your key is never committed. You can also put the key in a `.env` file instead (see below).

### 2. (Optional) Use a `.env` file for secrets
Copy `.env.example` to `.env` and fill it in. Environment variables override `config.yaml`:

```env
API_KEY=sk-or-...
BASE_URL=https://openrouter.ai/api/v1
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### 3. Install dependencies & run

The easiest way is to use the bundled launcher scripts (see next section), which handle the virtual environment for you. Or run manually:

```bash
# with uv (recommended)
uv sync
uv run dealcourier
#  ── or ──
uv run python -m dealcourier.main

# with plain pip
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS:    source .venv/bin/activate
pip install -e .
python -m dealcourier.main
```

### 4. Open the dashboard
On startup DealCourier prints the dashboard URL, e.g.:

```
Web dashboard: http://192.168.1.42:8000
```

Open it in your browser (locally `http://127.0.0.1:8000`). The database and log directories are created automatically on first run, and the default AI prompt templates are seeded.

> **First run note:** the scheduler starts but does **not** scrape immediately by default (`run_scrape_on_start: false`). After creating your first Search Item, go to the **Schedule** tab and click **Run Scrape**, or set `run_scrape_on_start: true` in `config.yaml`.

### One-click launchers
- **Windows:** double-click **`start.bat`** (or run it from a terminal).
- **macOS:** double-click **`start.command`** (or run `./start.command` in Terminal). The first time, macOS may gateblock it — right-click → *Open* → *Open* to allow it.

Both scripts: create/activate `.venv` if missing, install the project into it, then launch DealCourier and keep the window open so you can see logs and stop it with `Ctrl+C`.

---

## Configuration reference

All settings live in `config.yaml` (template: `config_init.yaml`). Environment variables override the file.

### AI backend (OpenAI-compatible)
DealCourier sends requests to any endpoint that speaks the OpenAI **Chat Completions** API. Just point it at your provider:

| Key | Meaning | Example |
|---|---|---|
| `api_key` | Your provider API key | `sk-or-...` |
| `base_url` | Provider's OpenAI-compatible base URL | `https://openrouter.ai/api/v1` |
| `default_model` | Model id for the high-volume listing-evaluation pass | `deepseek-v4-flash` |
| `terms_model` | Model id for the low-frequency search-term generation. Empty = reuse `default_model` | `z-ai/glm-5.2` |
| `ai_max_tokens` | Max tokens per AI response | `4096` |
| `ai_request_timeout_seconds` | HTTP timeout for AI calls | `60` |

**Common `base_url` values:**

| Provider | `base_url` | Model id style |
|---|---|---|
| OpenRouter | `https://openrouter.ai/api/v1` | `vendor/model`, e.g. `z-ai/glm-5.2`, `deepseek/deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini`, `gpt-4.1` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat`, `deepseek-reasoner` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| Together | `https://api.together.xyz/v1` | `meta-llama/...` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.2` |

**How the key is read** (`src/dealcourier/config.py`): on startup `load_config()` reads `config.yaml` with PyYAML, maps each key onto the `Config` dataclass, resolves `${VAR}` references from the environment, then applies environment overrides (`API_KEY`, `BASE_URL`, `DISCORD_WEBHOOK_URL`, `DEALCOURIER_HOST/PORT/DB`). `python-dotenv` loads `.env` first. The single provider client (`src/dealcourier/ai/providers/openai_compatible_provider.py`) is built once from `api_key` + `base_url` and reused for every call; only the `model` field changes between the eval pass (`default_model`) and term generation (`terms_model`).

**Cost tip:** because all calls go to one OpenAI-compatible backend, you can pick any cheap model for the bulk eval pass and a smarter one for term generation — both billed by the same provider. Search-term generation runs once per scrape cycle per search item (cheap), while every new listing triggers one eval call (the cost driver), so keep `default_model` cheap.

### Would an OpenRouter key work "exactly as well"?
Yes — and that's now the default. OpenRouter speaks the OpenAI Chat Completions API, so DealCourier treats it like any other OpenAI-compatible backend. The only thing to watch is the **model id format**: OpenRouter expects `vendor/model` (e.g. `z-ai/glm-5.2`, `deepseek/deepseek-chat`), whereas a direct OpenAI/DeepSeek key uses bare model names. Set `base_url` and the model ids to match your provider and it just works.

### Server
`host` (`0.0.0.0` = expose on LAN), `port` (default `8000`), `database_path`, `log_file`, `log_level`.

### Scheduler
`scrape_interval_minutes` (default `60`), `term_regeneration_interval_hours` (default `24`), `run_scrape_on_start` (default `false`). The interval can also be changed at runtime from the Schedule tab and is persisted across restarts.

### Scraper tuning
Per-marketplace request delays and term limits. Defaults are polite to avoid rate limiting. Ricardo in particular needs a long delay (`ricardo_delay_seconds: 30`).

### Notifications (Discord)
`discord_enabled`, `discord_webhook_url`, plus optional gating filters: `discord_min_value_factor`, `discord_min_profit`, `discord_max_distance_km`. See [Notifications](#notifications).

### Global filters
`global_min_price` / `global_max_price` (applied to all search items before AI eval; `0` = no limit), `skip_free_listings`.

---

## Setting up a product search

Go to the **Search Config** tab → **+ New Search Item**. A modal opens with the following fields.

### Fields

| Field | What it means |
|---|---|
| **Name** | The product you're hunting, e.g. `RTX 4060`. Always included as a search term verbatim. |
| **Platforms** | Which marketplaces to scrape for this item: Tutti, Ricardo, Anibis. (Independent of the global shop toggles in the Schedule tab — a shop must be enabled *globally* and *on the search item* to be scraped.) |
| **Specific Search Prompt** | Free-text guidance for generating **specific** search terms (exact model numbers, variants). E.g. *"Include OC / Ti variants and the laptop GPU suffixes."* |
| **General Search Prompt** | Guidance for **general**/broader terms (categories, synonyms, misspellings). E.g. *"Include 'Grafikkarte', 'GPU', 'nvidia 4060'."* |
| **Specific / General Terms Count** | How many terms of each kind the AI should generate. More terms = broader coverage but slower scrapes. Defaults `50`/`50`. |
| **Min Price / Max Price (CHF)** | Hard price bounds applied *before* the AI is called (saves tokens on obviously out-of-range listings). |
| **Min Profit (CHF)** | Only listings whose `estimated_value − price` is at least this are marked passed. |
| **Min Value Factor** | Only listings whose `estimated_value / price` is at least this are marked passed. `1.5` = item is worth ≥1.5× the asking price. |
| **Evaluation Hint** | Extra context appended to every eval call for this item. E.g. *"Desktop GPU only; typical new price ≈ 300 CHF; full value only with original box."* |
| **Knowledge Base** | Long-form reference material (markdown) prepended to every eval call. Great for niche categories where the model needs brand tiers, model lineups, condition guides, typical used prices. Because it's a stable prefix reused across every listing for this item, providers with prefix caching serve it at the cheap cache-hit rate after the first call. |
| **Custom Filters (one per line)** | Yes/no questions the AI answers per listing. Each must produce `{"passed": bool, "reason": "..."}`. A listing passes only if **every** filter passes. E.g. `Is this a standalone desktop GPU? Return true if yes.` / `Is this a laptop? Return false.` |

### A smart way to set them up

1. **Start narrow, then broaden.** Begin with one marketplace (Tutti is the fastest/cheapest to scrape) and modest term counts (specific `30`, general `20`). Once you see good results, add Ricardo/Anibis and raise counts.
2. **Always set Min/Max Price.** It's a free pre-filter that skips the AI call entirely for out-of-range listings. Use a generous band (e.g. 50–1500 CHF for a GPU) so you don't miss bundles.
3. **Set Min Value Factor around 1.3–1.5** to surface actual deals, not fairly-priced items. Combined with **Min Profit** (e.g. 50 CHF) so you only get pinged for things worth the hassle.
4. **Fill the Knowledge Base for niche items.** For mainstream goods the model already knows fair value; for specialist gear (sewing machines, audio gear, bike groupsets) paste a short markdown cheat-sheet of brand tiers and typical used prices. This dramatically improves valuation accuracy.
5. **Use Custom Filters to kill common false positives.** Searching "4060" will surface laptops with a 4060, phones, etc. Add filters like *"Is this a standalone GPU? true if yes."* and *"Is this a whole laptop or PC? return false."*
6. **Keep the Evaluation Hint short and specific** — the Knowledge Base is for the long stuff. The hint is for per-listing rules.
7. **Tune term counts to the marketplace.** Ricardo rate-limits hard, so high term counts make cycles very long. Keep `ricardo_max_terms` low (e.g. `10–20`) or leave `0` and control via the per-item counts.

After saving, click **Regenerate Terms** to preview what the AI came up with, then head to the Schedule tab and hit **Run Scrape**.

---

## The dashboard tabs

- **Listings** — Every scraped listing, with filters by platform, pass/fail status, price range, and sortable by date/price/estimated value/value factor/confidence/distance. Each card shows the AI's reasoning, components detected, and a link to the listing. Use **Unpass** on a card to manually throw out a listing the AI wrongly accepted.
- **Search Config** — Create / edit / delete Search Items (see above). **Regenerate Terms** triggers a fresh search-term generation for that item. The cached terms and their last-generated timestamp are shown.
- **Prompts** — Edit the system and user (Jinja2) prompt templates that drive search-term generation and listing evaluation. Useful for tuning how the AI reasons about value or what JSON it must return. Changes apply on the next scrape/eval cycle. The **Test** button renders a prompt with sample data and shows the AI's raw response.
- **Schedule** — Scheduler status and next-run times. **Actions:** *Run Scrape* (trigger an immediate cycle), *Eval All Unevaluated* (re-evaluate everything in the DB that was never evaluated), *Clear All Listings* (wipe the listings table), and a field to **set the scrape interval in minutes** (persisted across restarts). **Enabled Shops** lets you globally toggle Tutti/Ricardo/Anibis on or off. Below, the **Scrape Runs** history shows each cycle's found/new/evaluated/passed/notified counts and any errors.
- **Products** — The auto-built product knowledge base. As listings get evaluated, detected components and their values are aggregated here into a running reference of market prices and value trends. This is the same knowledge the eval pass consults via `get_product_context`.
- **Logs** — Live, filterable log stream (by level and free-text search) with an auto-scroll toggle. Mirrors what's written to `logs/dealcourier.log`.

---

## Notifications

DealCourier notifies via a **Discord webhook** (Pushbullet support has been removed — the self-hosted web UI is the interface).

To enable:
1. In Discord: channel → *Edit Channel* → *Integrations* → *Webhooks* → *New Webhook* → copy the URL.
2. Put the URL in `config.yaml` (`discord_webhook_url`) or `.env` (`DISCORD_WEBHOOK_URL`), and set `discord_enabled: true`.
3. Optionally set `discord_min_value_factor`, `discord_min_profit`, `discord_max_distance_km` to only notify on the best deals.

Notifications are color-coded by value factor (green ≥2×, orange ≥1.5×, blue otherwise) and include price, estimated value, profit, confidence, platform, location and distance from Zurich.

---

## Troubleshooting

- **"api_key not configured" in logs** — `api_key` is empty. Set it in `config.yaml` or `.env`. Remember `config.yaml` (not `config_init.yaml`) is the live file.
- **AI calls fail with HTTP 401/404** — wrong `base_url` or model id for your provider. Double-check the model id format (OpenRouter needs `vendor/model`).
- **No listings appear** — no enabled Search Items, or all globally-enabled shops are off. Check the Schedule tab.
- **Ricardo cycles are very slow** — that's expected; Ricardo rate-limits aggressively. Lower `ricardo_max_terms` or the per-item term counts.
- **Port already in use** — change `port` in `config.yaml` or set `DEALCOURIER_PORT`.
- **Rotating secrets** — `config.yaml` and `.env` are gitignored, but if you ever committed a key historically, rotate it immediately.

---

*DealCourier is a personal project. Use scraping responsibly and respect each marketplace's terms of service.*
