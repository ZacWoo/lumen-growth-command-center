# Lumen & Co — DTC Analytics Demo

A demonstration dashboard showing the analytics clarity I build for
direct-to-consumer e-commerce brands. **All data is synthetic** (a fictional
brand, "Lumen & Co") but engineered to behave like a real DTC business — with
seasonality, channel mix shift, and the kinds of problems real founders have.

A premium, Stripe-inspired **Growth Command Center** answering the questions
every DTC founder loses sleep over:

| Page | Question it answers |
|------|--------------------|
| **Overview** | Is growth healthy, profitable, repeatable? Executive diagnosis + Growth Quality Score |
| **Growth Quality** | How healthy is the growth, really? The 8-signal score breakdown |
| **Channels** | Which channels actually work, and where's the money burning? |
| **Retention** | Do customers come back, or am I refilling a leaky bucket? |
| **Unit Economics** | Am I making money per customer, or buying revenue at a loss? |
| **Funnel** | Where do buyers drop off before they pay? |
| **Recommendations** | What should we do next? Action backlog + Weekly Founder Memo |

> **Status:** ✅ All seven pages built with a shared premium design system
> (off-white canvas, deep-navy nav rail, blurple accents, soft-shadow cards).
> Productized features: **Growth Quality Score**, automated insights, benchmark
> lines, global filters (category · channel · campaign · customer type · region ·
> discount), and a one-click **Weekly Founder Memo** (in-app + Markdown download).
> Every figure is computed from the data at runtime.

## The story in the data

This brand looks healthy on top-line revenue but is quietly addicted to its
worst-performing channel:

- Revenue grows ~2.5×, but ~65% of it still comes from brand-new customers every
  month — growth is *rented, not owned*.
- **Meta Prospecting** has nearly the lowest CAC, gets the biggest budget, but
  has the **worst repeat rate (~21%)** — it buys one-time discount-seekers.
- **Email/Organic** and **Referral** cost a fraction and return 9–11× — and are
  under-funded.
- Cohort retention is *deteriorating* as the paid mix grows.
- Meta Prospecting also leaks hardest at checkout (~47% completion vs ~79% for
  Referral).

## Run locally

```bash
pip install -r requirements.txt
streamlit run Overview.py
```

## Deploy free on Streamlit Community Cloud

1. Push this folder to a public GitHub repo.
2. Go to share.streamlit.io → New app → point at your repo.
3. Set the main file to `Overview.py`. Done — you get a public URL.

## Regenerate / tune the data

`generate_data.py` (in the repo root, one level up) is deterministic (seed 42).
The channel parameters at the top control every embedded insight — tune them and
re-run to make the story sharper or subtler.

## Stack

Python · pandas · NumPy · Streamlit · Plotly. No warehouse needed at this scale;
a client version connects directly to Shopify / Meta Ads / Klaviyo exports or a
small BigQuery/DuckDB layer.
