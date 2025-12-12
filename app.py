# app.py — Strength Meter PRO (Full functional, Neon Artefact Bar Scroller)
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore

# ----------------------------
# CONFIG
# ----------------------------
CONFIG = {
    'tickers': {
        # FX major & crosses (add/remove as you want)
        'EURUSD=X': [20.0, 'EUR', 'USD', 'FX'],
        'USDJPY=X': [15.0, 'USD', 'JPY', 'FX'],
        'GBPUSD=X': [10.0, 'GBP', 'USD', 'FX'],
        'AUDUSD=X': [6.0, 'AUD', 'USD', 'FX'],
        'USDCAD=X': [5.0, 'USD', 'CAD', 'FX'],
        'USDCHF=X': [4.0, 'USD', 'CHF', 'FX'],
        'NZDUSD=X': [3.0, 'NZD', 'USD', 'FX'],
        'EURGBP=X': [3.0, 'EUR', 'GBP', 'FX'],
        'EURJPY=X': [3.0, 'EUR', 'JPY', 'FX'],
        'GBPJPY=X': [3.0, 'GBP', 'JPY', 'FX'],
        'AUDJPY=X': [2.0, 'AUD', 'JPY', 'FX'],
        'EURAUD=X': [2.0, 'EUR', 'AUD', 'FX'],
        'EURCHF=X': [2.0, 'EUR', 'CHF', 'FX'],
        # Metals
        'GC=F': [8.0, 'XAU', 'USD', 'METAL'],
        'PL=F': [2.0, 'XPT', 'USD', 'METAL'],
        # Indices
        '^DJI': [8.0, 'US30', 'USD', 'INDEX'],
        '^IXIC': [8.0, 'NAS100', 'USD', 'INDEX'],
        '^GSPC': [10.0, 'SPX500', 'USD', 'INDEX'],
    },
    'period': '60d',
    'interval': '1d',
    'lookback_days': 3,
    'atr_period': 14,
    'atr_floor_pct': 1e-4,
    'smoothing_span': 3,
    'category_mode': True
}

# ----------------------------
# UTIL: ATR
# ----------------------------
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

# ----------------------------
# Neon color mapping
# ----------------------------
def neon_color(score):
    # score in 0..10
    try:
        s = float(score)
    except Exception:
        s = 5.0
    if s <= 3:
        return '#ff005e'  # neon red
    elif s <= 5:
        return '#ff7a20'  # neon orange
    elif s <= 7:
        return '#ffea00'  # neon yellow
    elif s <= 9:
        return '#00ff9d'  # neon green
    else:
        return '#00eaff'  # neon cyan (highest)

# ----------------------------
# CORE: compute_strength
# ----------------------------
def compute_strength(config=CONFIG):
    tickers_cfg = config['tickers']
    lookback = config['lookback_days']
    atr_period = config['atr_period']
    atr_floor_pct = config['atr_floor_pct']

    all_tickers = list(tickers_cfg.keys())

    # Download data (yfinance supports multiple tickers)
    try:
        data = yf.download(all_tickers, period=config['period'], interval=config['interval'],
                           group_by='ticker', progress=False, threads=True)
    except Exception as e:
        st.error(f"Erreur téléchargement yfinance: {e}")
        return pd.DataFrame(), {}

    # Determine unique entities (currencies / XAU / indices etc.)
    entities = set()
    for t, v in tickers_cfg.items():
        entities.add(v[1])
        entities.add(v[2])

    scores_acc = {e: {'weighted_sum': 0.0, 'total_weight': 0.0} for e in entities}
    categories = {}
    if config['category_mode']:
        for t, v in tickers_cfg.items():
            cat = v[3]
            if cat not in categories:
                categories[cat] = {e: {'weighted_sum': 0.0, 'total_weight': 0.0} for e in entities}

    # For each ticker compute strength contribution
    for ticker, info in tickers_cfg.items():
        weight, base, quote, category = info

        # Skip if data missing
        try:
            if ticker not in data.columns.get_level_values(0):
                continue
            df = data[ticker].dropna()
        except Exception:
            # Single ticker frame shape might be different
            try:
                # fallback: if data is not multiindexed (single ticker)
                df = data.dropna()
            except Exception:
                continue

        if df.empty or len(df) < max(atr_period + 2, lookback + 2):
            continue

        close = df['Close']
        price_now = close.iloc[-1]
        price_past = close.shift(lookback).iloc[-1]
        if pd.isna(price_now) or pd.isna(price_past) or price_past == 0:
            continue

        raw_move_pct = (price_now - price_past) / price_past

        atr = calculate_atr(df, period=atr_period)
        current_atr = atr.iloc[-1]
        atr_pct = current_atr / price_now if price_now != 0 else atr_floor_pct
        if pd.isna(atr_pct) or atr_pct <= 0:
            atr_pct = atr_floor_pct
        atr_pct = max(atr_pct, atr_floor_pct)

        strength = raw_move_pct / atr_pct

        scores_acc[base]['weighted_sum'] += strength * weight
        scores_acc[base]['total_weight'] += weight
        scores_acc[quote]['weighted_sum'] += (-strength) * weight
        scores_acc[quote]['total_weight'] += weight

        if config['category_mode']:
            categories[category][base]['weighted_sum'] += strength * weight
            categories[category][base]['total_weight'] += weight
            categories[category][quote]['weighted_sum'] += (-strength) * weight
            categories[category][quote]['total_weight'] += weight

    # Raw values
    raw_values = {}
    for ent, v in scores_acc.items():
        raw_values[ent] = v['weighted_sum'] / v['total_weight'] if v['total_weight'] > 0 else 0.0

    df_raw = pd.Series(raw_values, name='raw_strength').to_frame()

    # z-score normalization and scale to 0..10 (same logic as before)
    vals = df_raw['raw_strength'].values
    if np.nanstd(vals) == 0:
        z = np.zeros_like(vals)
    else:
        z = zscore(vals, nan_policy='omit')
    z = np.nan_to_num(z)
    z = np.clip(z, -3, 3)
    scaled = 5 + (z / 6) * 10
    scaled = np.clip(scaled, 0, 10)

    df_raw['score'] = np.round(scaled, 2)

    if config['smoothing_span'] > 1:
        df_raw['score_smoothed'] = df_raw['score'].ewm(span=config['smoothing_span'], adjust=False).mean()
    else:
        df_raw['score_smoothed'] = df_raw['score']

    df_raw = df_raw.sort_values(by='score_smoothed', ascending=False)

    # Also prepare category frames (optional)
    category_frames = {}
    if config['category_mode']:
        for cat, acc in categories.items():
            tmp = {}
            for ent, v in acc.items():
                tmp[ent] = v['weighted_sum'] / v['total_weight'] if v['total_weight'] > 0 else 0.0
            s = pd.Series(tmp)
            if s.std() == 0:
                zc = np.zeros_like(s.values)
            else:
                zc = zscore(s.values, nan_policy='omit')
            zc = np.clip(np.nan_to_num(zc), -3, 3)
            scaled_c = 5 + (zc / 6) * 10
            scaled_c = np.clip(scaled_c, 0, 10)
            category_frames[cat] = pd.DataFrame({'score': np.round(scaled_c, 2)}, index=s.index).sort_values(by='score', ascending=False)

    return df_raw, category_frames

# ----------------------------
# STREAMLIT UI + STYLES
# ----------------------------
st.set_page_config(page_title="Strength Meter PRO", layout="wide")
st.title("Strength Meter PRO — Artefact NEON")

st.markdown("""
<style>
/* Page background */
[data-testid="stAppViewContainer"] { background-color: #050505; color: #e0fff5; }
/* Container for bars */
.bar-container { display:flex; flex-direction:column; gap:10px; margin-top:12px; }
/* Single bar item */
.bar-item {
  display:flex; align-items:center; gap:12px;
  padding:10px 14px; border-radius:10px;
  background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
  border: 1px solid rgba(255,255,255,0.04);
  box-shadow: 0 6px 18px rgba(0,0,0,0.6);
}
/* left label */
.bar-label { width:110px; font-weight:700; font-size:15px; color:#bfffe8; }
/* neon bar track */
.neon-bar { flex:1; height:18px; border-radius:12px; overflow:hidden; background:#0b0b0b; box-shadow: inset 0 1px 0 rgba(255,255,255,0.02); }
/* fill */
.neon-fill { height:100%; border-radius:12px; transition: width 0.45s ease, box-shadow 0.3s ease; }
/* score */
.score-text { width:70px; text-align:right; font-weight:700; color:#9fffe0; }
/* small caption */
.small { font-size:13px; color:#9fbfb2; margin-top:8px; }
/* responsive */
@media (max-width:700px) {
  .bar-label { width:80px; font-size:13px; }
  .score-text { width:56px; font-size:14px; }
}
</style>
""", unsafe_allow_html=True)

st.markdown("**Description:** Artefact-style neon scroller affichant entités et paires. Calcul basé sur ATR + zscore, score 0→10 (smoothed).")
st.markdown("---")

# ----------------------------
# ACTION
# ----------------------------
if st.button("Calculer"):
    with st.spinner("Téléchargement et calcul en cours..."):
        df_entities, cats = compute_strength(CONFIG)

    if df_entities is None or df_entities.empty:
        st.error("Aucune donnée calculée — vérifie la connexion yfinance ou la configuration des tickers.")
    else:
        # ENTITIES section
        st.subheader("Entities — Strength (smoothed)")
        st.markdown("<div class='bar-container'>", unsafe_allow_html=True)
        for ent in df_entities.index:
            score = float(df_entities.loc[ent, 'score_smoothed'])
            pct = max(min(score / 10.0, 1.0), 0.0) * 100
            color = neon_color(score)
            # build HTML per bar
            bar_html = f"""
            <div class='bar-item'>
                <div class='bar-label'>{ent}</div>
                <div class='neon-bar'>
                    <div class='neon-fill' style='width:{pct}%; background:{color}; box-shadow: 0 0 14px {color};'></div>
                </div>
                <div class='score-text'>{score:.2f}</div>
            </div>
            """
            st.markdown(bar_html, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")
        # PAIRS / TICKERS section
        st.subheader("Pairs & Assets (approx. from entity difference)")

        # Build a DataFrame for pairs (ticker wise)
        pairs_list = []
        for ticker, info in CONFIG['tickers'].items():
            weight, base, quote, category = info
            # If both entities present compute pair score as base - quote (smoothed)
            if base in df_entities.index and quote in df_entities.index:
                base_s = float(df_entities.loc[base, 'score_smoothed'])
                quote_s = float(df_entities.loc[quote, 'score_smoothed'])
                diff = base_s - quote_s  # in approx -10..10
                # normalize diff (-10..10) -> 0..10
                pair_score = (diff + 10.0) / 20.0 * 10.0
                pair_score = float(np.clip(pair_score, 0.0, 10.0))
            else:
                # fallback neutral
                pair_score = 5.0
            pairs_list.append({'ticker': ticker, 'base': base, 'quote': quote, 'score': round(pair_score, 3), 'category': category})

        df_pairs = pd.DataFrame(pairs_list).sort_values(by='score', ascending=False).reset_index(drop=True)

        # render bars for pairs
        st.markdown("<div class='bar-container'>", unsafe_allow_html=True)
        for _, row in df_pairs.iterrows():
            ticker = row['ticker']
            score = float(row['score'])
            pct = max(min(score / 10.0, 1.0), 0.0) * 100
            color = neon_color(score)
            html = f"""
            <div class='bar-item'>
                <div class='bar-label'>{ticker}</div>
                <div class='neon-bar'>
                    <div class='neon-fill' style='width:{pct}%; background:{color}; box-shadow: 0 0 14px {color};'></div>
                </div>
                <div class='score-text'>{score:.2f}</div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # allow download of CSV combining entities + pairs
        out_entities = df_entities.reset_index().rename(columns={'index': 'entity'})
        out_pairs = df_pairs.copy()
        # merge or output two files combined in a zip? for simplicity combine in one CSV with a section header
        csv_buf = "== ENTITIES ==\n" + out_entities.to_csv(index=False) + "\n== PAIRS ==\n" + out_pairs.to_csv(index=False)
        st.download_button("Télécharger résultats (CSV)", csv_buf.encode('utf-8'), file_name='strength_results.csv', mime='text/csv')

        # Optionally show categories
        if cats:
            st.markdown("---")
            st.subheader("Par catégorie")
            for cat_name, frame in cats.items():
                st.markdown(f"**{cat_name}**")
                st.dataframe(frame.style.highlight_max(axis=0), height=250)

else:
    st.info("Cliquez sur 'Calculer' pour lancer l'analyse (yfinance).")

# ----------------------------
# FOOTER / THEME INSTRUCTIONS
# ----------------------------
st.markdown("---")
st.markdown("<div class='small'>Thème: fond dark. Pour activer thème Streamlit global, crée .streamlit/config.toml (voir docs).</div>", unsafe_allow_html=True)


