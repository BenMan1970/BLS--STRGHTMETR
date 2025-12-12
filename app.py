import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------
CONFIG = {
    'tickers': {
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
        'GC=F': [8.0, 'XAU', 'USD', 'METAL'],
        'PL=F': [2.0, 'XPT', 'USD', 'METAL'],
        '^DJI': [8.0, 'US30', 'USD', 'INDEX'],
        '^IXIC': [8.0, 'NAS100', 'USD', 'INDEX'],
        '^GSPC': [10.0, 'SPX500', 'USD', 'INDEX']
    },
    'period': '60d',
    'interval': '1d',
    'lookback_days': 3,
    'atr_period': 14,
    'atr_floor_pct': 1e-4,
    'smoothing_span': 3,
    'category_mode': True
}

# ------------------------------------------------------------
# UTILS
# ------------------------------------------------------------
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

# ------------------------------------------------------------
# CORE
# ------------------------------------------------------------
def compute_strength(config=CONFIG):
    tickers_cfg = config['tickers']
    lookback = config['lookback_days']
    atr_period = config['atr_period']
    atr_floor_pct = config['atr_floor_pct']

    all_tickers = list(tickers_cfg.keys())
    data = yf.download(all_tickers, period=config['period'], interval=config['interval'], group_by='ticker', progress=False)

    entities = set()
    for t, v in tickers_cfg.items():
        entities.add(v[1])
        entities.add(v[2])

    scores_acc = {e: {'weighted_sum': 0, 'total_weight': 0} for e in entities}

    categories = {}
    if config['category_mode']:
        for t, v in tickers_cfg.items():
            cat = v[3]
            if cat not in categories:
                categories[cat] = {e: {'weighted_sum': 0, 'total_weight': 0} for e in entities}

    for ticker, info in tickers_cfg.items():
        weight, base, quote, category = info

        if ticker not in data.columns.get_level_values(0):
            continue

        df = data[ticker].dropna()
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

    raw_values = {}
    for ent, v in scores_acc.items():
        raw_values[ent] = v['weighted_sum'] / v['total_weight'] if v['total_weight'] > 0 else 0

    df_raw = pd.Series(raw_values, name='raw_strength').to_frame()

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

    category_frames = {}
    if config['category_mode']:
        for cat, acc in categories.items():
            tmp = {}
            for ent, v in acc.items():
                tmp[ent] = v['weighted_sum'] / v['total_weight'] if v['total_weight'] > 0 else 0
            s = pd.Series(tmp)
            if s.std() == 0:
                zc = np.zeros_like(s.values)
            else:
                zc = zscore(s.values, nan_policy='omit')
            zc = np.clip(np.nan_to_num(zc), -3, 3)
            scaled_c = 5 + (zc / 6) * 10
            scaled_c = np.clip(scaled_c, 0, 10)
            category_frames[cat] = pd.DataFrame({'score': scaled_c}, index=s.index).sort_values(by='score', ascending=False)

    return df_raw, category_frames

# ------------------------------------------------------------
# STREAMLIT APP
# ------------------------------------------------------------
st.title("Strength Meter PRO")
st.write("Analyse multi-actifs pondérée avec ATR et normalisation z-score.")

if st.button("Calculer"):
    df, cats = compute_strength(CONFIG)
    st.subheader("Classement global")
    st.dataframe(df)

    for cat, d in cats.items():
        st.subheader(f"Catégorie : {cat}")
        st.dataframe(d)
