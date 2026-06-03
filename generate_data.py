"""
Synthetic DTC e-commerce data generator
=========================================
Produces realistic, internally-consistent data for a fictional DTC brand
("Lumen & Co", a premium home-goods brand) across ~20 months.

The data is deliberately engineered so that a dashboard built on it can answer
five founder questions AND contain discoverable, non-obvious insights:

  1. OVERVIEW   - Revenue grows, but growth is increasingly carried by paid
                  acquisition rather than returning customers (growth quality issue).
  2. UNIT ECON  - Blended LTV:CAC sits around ~2.1:1 (below the healthy 3:1),
                  and payback is creeping up.
  3. CHANNELS   - "Meta Prospecting" has the LOWEST CAC but the WORST repeat
                  rate -> it looks cheapest but is the least valuable.
                  "Email/Organic" has higher CAC but the best LTV.
                  "Google Brand" looks great on ROAS but is mostly cannibalizing
                  organic demand.
  4. RETENTION  - Repeat purchase rate ~28%; cohort curves show a steep drop after
                  the first order, with later cohorts retaining worse (leaky bucket
                  getting leakier as paid mix rises).
  5. FUNNEL     - One channel (Meta Prospecting) drives high traffic but craters at
                  the checkout step (a discoverable "leak").

Tables written to /home/claude/data/:
  customers.csv, orders.csv, ad_spend.csv, funnel.csv
Deterministic via SEED.
"""

import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta
import os

SEED = 42
np.random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)

START = datetime(2024, 1, 1)
END = datetime(2025, 8, 31)
N_DAYS = (END - START).days + 1
dates = [START + timedelta(days=i) for i in range(N_DAYS)]

# ----------------------------------------------------------------------------
# Channel definitions. These parameters ENCODE the insights.
#   cac          : acquisition cost per customer (mean)
#   repeat_mult  : multiplier on baseline repeat propensity (the punchline:
#                  cheapest channel = worst repeat)
#   aov_mult     : multiplier on average order value
#   growth       : how fast this channel's volume grows over the window
#   checkout_mult: funnel checkout-completion multiplier (Meta has the leak)
# ----------------------------------------------------------------------------
CHANNELS = {
    "Meta Prospecting": dict(share0=0.22, cac=18, repeat_mult=0.55, aov_mult=0.92,
                             growth=2.6, checkout_mult=0.72),   # cheap, churns, leaks
    "Meta Retargeting": dict(share0=0.12, cac=26, repeat_mult=1.05, aov_mult=1.02,
                             growth=1.9, checkout_mult=1.05),
    "Google Brand":     dict(share0=0.10, cac=22, repeat_mult=1.10, aov_mult=1.08,
                             growth=1.4, checkout_mult=1.12),   # looks great, cannibalizes
    "Google Shopping":  dict(share0=0.14, cac=31, repeat_mult=0.95, aov_mult=1.00,
                             growth=1.6, checkout_mult=1.00),
    "Email/Organic":    dict(share0=0.20, cac=9,  repeat_mult=1.65, aov_mult=1.12,
                             growth=1.1, checkout_mult=1.15),   # best LTV, underfunded
    "TikTok":           dict(share0=0.10, cac=20, repeat_mult=0.70, aov_mult=0.88,
                             growth=2.2, checkout_mult=0.85),
    "Referral":         dict(share0=0.12, cac=7,  repeat_mult=1.55, aov_mult=1.10,
                             growth=1.3, checkout_mult=1.18),
}
channel_names = list(CHANNELS.keys())

BASE_AOV = 68.0          # baseline average order value
GROSS_MARGIN = 0.62      # COGS = 38% of revenue (before discounts)

# ----------------------------------------------------------------------------
# Seasonality + growth multiplier for daily new-customer volume
# ----------------------------------------------------------------------------
def daily_volume_multiplier(d: datetime) -> float:
    t = (d - START).days / N_DAYS
    trend = 1.0 + 1.5 * t                      # ~2.5x growth over the window
    doy = d.timetuple().tm_yday
    # annual seasonality: summer dip, Q4 holiday spike
    seasonal = 1.0 + 0.18 * np.sin(2 * np.pi * (doy - 80) / 365)
    if d.month == 11:                          # BFCM spike
        seasonal *= 1.55 if d.day >= 20 else 1.25
    if d.month == 12 and d.day <= 20:
        seasonal *= 1.35
    if d.month in (6, 7):                       # summer slump
        seasonal *= 0.9
    return trend * seasonal

# channel mix shifts toward paid prospecting over time (drives growth-quality insight)
def channel_share(d: datetime):
    t = (d - START).days / N_DAYS
    raw = {}
    for ch, p in CHANNELS.items():
        # growth>1.5 channels gain share over time
        raw[ch] = p["share0"] * (1 + (p["growth"] - 1) * t)
    s = sum(raw.values())
    return {ch: v / s for ch, v in raw.items()}

BASE_NEW_PER_DAY = 42

# ----------------------------------------------------------------------------
# 1) CUSTOMERS  — assign acquisition date, channel, CAC, region
# ----------------------------------------------------------------------------
cust_rows = []
cid = 0
for d in dates:
    n = np.random.poisson(BASE_NEW_PER_DAY * daily_volume_multiplier(d))
    shares = channel_share(d)
    chs = np.random.choice(channel_names, size=n, p=list(shares.values()))
    for ch in chs:
        p = CHANNELS[ch]
        cac = max(2.0, np.random.normal(p["cac"], p["cac"] * 0.22))
        cust_rows.append((
            cid, d.date().isoformat(), ch, round(cac, 2),
            np.random.choice(["West", "South", "Midwest", "Northeast"],
                             p=[0.32, 0.30, 0.18, 0.20])
        ))
        cid += 1

customers = pd.DataFrame(cust_rows, columns=[
    "customer_id", "first_order_date", "acquisition_channel",
    "acquisition_cost", "region"
])
print(f"customers: {len(customers):,}")

# ----------------------------------------------------------------------------
# 2) ORDERS — first order on acquisition date, then repeat orders driven by
#    channel repeat_mult, with later cohorts retaining slightly worse.
# ----------------------------------------------------------------------------
order_rows = []
oid = 0
END_DATE = END.date()

for r in customers.itertuples(index=False):
    p = CHANNELS[r.acquisition_channel]
    first_dt = datetime.fromisoformat(r.first_order_date).date()

    def make_order(dt, is_first):
        global oid
        aov = max(12, np.random.normal(BASE_AOV * p["aov_mult"], BASE_AOV * 0.28))
        # discounts more common on first order / promo channels
        disc_rate = np.random.choice([0, 0.1, 0.15, 0.2],
                                     p=[0.55, 0.22, 0.15, 0.08])
        if is_first and r.acquisition_channel in ("Meta Prospecting", "TikTok"):
            disc_rate = np.random.choice([0.1, 0.15, 0.2, 0.25],
                                         p=[0.25, 0.30, 0.30, 0.15])
        revenue = round(aov, 2)
        discount = round(revenue * disc_rate, 2)
        cogs = round(revenue * (1 - GROSS_MARGIN), 2)
        order_rows.append((oid, r.customer_id, dt.isoformat(), revenue,
                           discount, cogs, r.acquisition_channel, is_first))
        oid += 1

    # first order
    make_order(first_dt, True)

    # repeat behavior --------------------------------------------------------
    # later cohorts retain worse: cohort penalty grows through the window
    cohort_t = (first_dt - START.date()).days / N_DAYS
    cohort_penalty = 1.0 - 0.22 * cohort_t
    base_repeat_p = 0.30 * p["repeat_mult"] * cohort_penalty
    base_repeat_p = float(np.clip(base_repeat_p, 0.02, 0.85))

    # number of additional orders ~ geometric-ish, scaled by repeat propensity
    n_repeat = np.random.poisson(base_repeat_p * 2.2)
    last_dt = first_dt
    for _ in range(n_repeat):
        # time to next order: shorter for high-repeat channels
        gap = int(max(7, np.random.exponential(55 / max(0.5, p["repeat_mult"]))))
        nxt = last_dt + timedelta(days=gap)
        if nxt > END_DATE:
            break
        make_order(nxt, False)
        last_dt = nxt

orders = pd.DataFrame(order_rows, columns=[
    "order_id", "customer_id", "order_date", "revenue", "discount",
    "cogs", "channel", "is_first_order"
])
print(f"orders: {len(orders):,}")
repeat_rate = customers.shape[0] and (
    orders[~orders.is_first_order].customer_id.nunique() / customers.shape[0]
)
print(f"overall repeat purchase rate: {repeat_rate:.1%}")

# ----------------------------------------------------------------------------
# 3) AD SPEND — daily spend by channel, reverse-engineered from acquired
#    customers * CAC, with realistic impressions/clicks. Organic/Referral
#    carry little/no paid spend (so their effective CAC looks great).
# ----------------------------------------------------------------------------
first_orders = orders[orders.is_first_order].merge(
    customers[["customer_id", "acquisition_channel", "acquisition_cost"]],
    on="customer_id"
)
first_orders["d"] = first_orders["order_date"]

spend_rows = []
grp = first_orders.groupby(["d", "acquisition_channel"]).agg(
    new_customers=("customer_id", "count"),
    spend=("acquisition_cost", "sum")
).reset_index()

PAID = {"Meta Prospecting", "Meta Retargeting", "Google Brand",
        "Google Shopping", "TikTok"}
for r in grp.itertuples(index=False):
    ch = r.acquisition_channel
    if ch in PAID:
        spend = round(r.spend, 2)
    elif ch == "Email/Organic":
        spend = round(r.spend * 0.15, 2)   # mostly free; small tooling cost
    else:  # Referral
        spend = round(r.spend * 0.5, 2)    # referral incentive payouts
    # rough impressions/clicks consistent with spend and channel CPCs
    cpc = {"Meta Prospecting": 0.9, "Meta Retargeting": 1.3, "Google Brand": 0.6,
           "Google Shopping": 1.1, "TikTok": 0.7, "Email/Organic": 0.05,
           "Referral": 0.2}[ch]
    clicks = int(spend / cpc) if cpc else 0
    ctr = {"Meta Prospecting": 0.012, "Meta Retargeting": 0.022,
           "Google Brand": 0.08, "Google Shopping": 0.03, "TikTok": 0.009,
           "Email/Organic": 0.04, "Referral": 0.05}[ch]
    impressions = int(clicks / ctr) if ctr else 0
    spend_rows.append((r.d, ch, spend, impressions, clicks, int(r.new_customers)))

ad_spend = pd.DataFrame(spend_rows, columns=[
    "date", "channel", "spend", "impressions", "clicks", "new_customers"
]).sort_values(["date", "channel"])
print(f"ad_spend rows: {len(ad_spend):,}")

# ----------------------------------------------------------------------------
# 4) FUNNEL — daily sessions -> product_views -> add_to_cart ->
#    checkout_started -> purchased, by channel. Purchases tie back (approx)
#    to actual new+repeat orders that day. Meta Prospecting leaks at checkout.
# ----------------------------------------------------------------------------
orders["order_date_dt"] = pd.to_datetime(orders["order_date"])
daily_orders = orders.groupby([orders.order_date, "channel"]).size().reset_index(
    name="purchased")
daily_orders.columns = ["date", "channel", "purchased"]

funnel_rows = []
for r in daily_orders.itertuples(index=False):
    p = CHANNELS[r.channel]
    purchased = int(r.purchased)
    if purchased == 0:
        continue
    # work backwards up the funnel with channel-specific checkout leak
    checkout_conv = float(np.clip(np.random.normal(0.65 * p["checkout_mult"], 0.04),
                                  0.2, 0.95))
    checkout_started = int(purchased / checkout_conv)
    atc = int(checkout_started / np.clip(np.random.normal(0.62, 0.04), 0.3, 0.9))
    pviews = int(atc / np.clip(np.random.normal(0.38, 0.04), 0.2, 0.7))
    sessions = int(pviews / np.clip(np.random.normal(0.55, 0.05), 0.3, 0.8))
    funnel_rows.append((r.date, r.channel, sessions, pviews, atc,
                        checkout_started, purchased))

funnel = pd.DataFrame(funnel_rows, columns=[
    "date", "channel", "sessions", "product_views", "add_to_cart",
    "checkout_started", "purchased"
]).sort_values(["date", "channel"])
print(f"funnel rows: {len(funnel):,}")

# ============================================================================
# DIMENSION ENRICHMENT — product category, campaign, device.
# Added AFTER the core tables are built, using INDEPENDENT RNG streams
# (np.random.default_rng) so the global np.random state — and therefore every
# core metric (revenue, CAC, repeat rate, funnel conversion) — is untouched and
# byte-for-byte reproducible. These columns are labels/splits only.
# ----------------------------------------------------------------------------

# --- product_category on orders (premium home-goods catalogue) --------------
rng_cat = np.random.default_rng(20240601)
CATEGORIES = ["Lighting", "Bedding", "Bath", "Tableware", "Decor", "Furniture"]
CAT_WEIGHTS = [0.20, 0.22, 0.11, 0.16, 0.19, 0.12]
orders["product_category"] = rng_cat.choice(
    CATEGORIES, size=len(orders), p=CAT_WEIGHTS)
print(f"product categories: {orders.product_category.nunique()}")

# --- campaign on customers (a few named campaigns per channel) --------------
rng_camp = np.random.default_rng(20240602)
CAMPAIGNS = {
    "Meta Prospecting": ["Lookalike 1%", "Broad Interest", "Advantage+ Shopping"],
    "Meta Retargeting": ["30-Day Site Visitors", "Cart Abandoners"],
    "Google Brand":     ["Brand — Exact", "Brand — Phrase"],
    "Google Shopping":  ["Performance Max", "Standard Shopping"],
    "TikTok":           ["Spark Ads", "Creator UGC", "Trending Sounds"],
    "Email/Organic":    ["Newsletter", "Organic Search", "Direct"],
    "Referral":         ["Friend Referral", "Influencer Code"],
}
customers["campaign"] = ""
for ch, camps in CAMPAIGNS.items():
    idx = customers.index[customers.acquisition_channel == ch]
    customers.loc[idx, "campaign"] = rng_camp.choice(camps, size=len(idx))

# propagate campaign onto orders via customer_id (handy for filtering)
orders = orders.merge(customers[["customer_id", "campaign"]],
                      on="customer_id", how="left")

# --- device split on funnel -------------------------------------------------
# Expand each (date, channel) funnel row into per-device rows. Counts are
# allocated with largest-remainder rounding so each step's per-channel totals
# stay EXACTLY equal to the original funnel (device is a clean decomposition).
# Mobile carries a mild checkout-completion penalty (realistic), redistributed
# so the channel's total purchased is preserved.
rng_dev = np.random.default_rng(20240603)
DEVICES = ["Mobile", "Desktop", "Tablet"]
BASE_MIX = np.array([0.60, 0.33, 0.07])
MOBILE_TILT = {  # additive shift toward mobile for social/low-intent channels
    "Meta Prospecting": 0.14, "TikTok": 0.16, "Meta Retargeting": 0.08,
    "Google Shopping": 0.0, "Google Brand": -0.06, "Email/Organic": -0.04,
    "Referral": -0.02,
}
# relative purchase-completion efficiency by device (mobile leaks more)
DEVICE_COMPL = np.array([0.90, 1.16, 1.02])


def largest_remainder(total, weights):
    """Integer allocation of `total` across buckets ~ weights, summing exactly."""
    w = np.asarray(weights, dtype=float)
    w = w / w.sum() if w.sum() else np.ones_like(w) / len(w)
    raw = w * total
    base = np.floor(raw).astype(int)
    rem = total - base.sum()
    if rem > 0:
        order = np.argsort(-(raw - base))
        for i in range(rem):
            base[order[i % len(base)]] += 1
    return base


funnel_steps = ["sessions", "product_views", "add_to_cart", "checkout_started"]
dev_rows = []
for r in funnel.itertuples(index=False):
    tilt = MOBILE_TILT.get(r.channel, 0.0)
    mix = BASE_MIX + np.array([tilt, -tilt * 0.7, -tilt * 0.3])
    mix = np.clip(mix, 0.02, None)
    mix = mix / mix.sum()
    # allocate the upper-funnel steps proportionally to the device mix
    alloc = {s: largest_remainder(getattr(r, s), mix) for s in funnel_steps}
    # allocate purchases weighted by checkout_started * device efficiency
    purch_w = alloc["checkout_started"] * DEVICE_COMPL
    purch = largest_remainder(r.purchased, purch_w if purch_w.sum() else mix)
    for di, dev in enumerate(DEVICES):
        dev_rows.append((
            r.date, r.channel, dev,
            int(alloc["sessions"][di]), int(alloc["product_views"][di]),
            int(alloc["add_to_cart"][di]), int(alloc["checkout_started"][di]),
            int(purch[di])))

funnel = pd.DataFrame(dev_rows, columns=[
    "date", "channel", "device", "sessions", "product_views",
    "add_to_cart", "checkout_started", "purchased"]).sort_values(
    ["date", "channel", "device"])
print(f"funnel rows (with device): {len(funnel):,}")

# ----------------------------------------------------------------------------
# Write outputs
# ----------------------------------------------------------------------------
customers.to_csv(f"{OUT}/customers.csv", index=False)
orders.drop(columns=["order_date_dt"]).to_csv(f"{OUT}/orders.csv", index=False)
ad_spend.to_csv(f"{OUT}/ad_spend.csv", index=False)
funnel.to_csv(f"{OUT}/funnel.csv", index=False)
print("\nWrote customers.csv, orders.csv, ad_spend.csv, funnel.csv to", OUT)
