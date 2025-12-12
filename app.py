# app.py — Strength Meter PRO (Thermomètres Aquarelle Vibrants)
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore
import plotly.express as px

# ----------------------------
# CONFIG
# ----------------------------
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
# CORE: compute_strength
# ----------------------------
@st.cache_data(ttl=300)
def compute_strength(config=CONFIG):
    tickers_cfg = config['tickers']
    lookback = config['lookback_days']
    atr_period = config['atr_period']
    atr_floor_pct = config['atr_floor_pct']
    all_tickers = list(tickers_cfg.keys())
    try:
        data = yf.download(all_tickers, period=config['period'], interval=config['interval'],
                           progress=False, threads=False)
    except Exception as e:
        st.error(f"❌ Erreur téléchargement yfinance: {e}")
        return pd.DataFrame(), {}
    
    entities = set()
    categories = {'FX': {}, 'METAL': {}, 'INDEX': {}}
    for t, v in tickers_cfg.items():
        entities.add(v[1])
        entities.add(v[2])
        cat = v[3]
        if cat in categories:
            if v[1] not in categories[cat]:
                categories[cat][v[1]] = {'weighted_sum': 0.0, 'total_weight': 0.0}
            if v[2] not in categories[cat]:
                categories[cat][v[2]] = {'weighted_sum': 0.0, 'total_weight': 0.0}
    
    scores_acc = {e: {'weighted_sum': 0.0, 'total_weight': 0.0} for e in entities}
    
    for ticker, info in tickers_cfg.items():
        weight, base, quote, category = info
        if ticker not in data.columns.get_level_values(1):
            continue
        df = data.xs(ticker, level=1, axis=1).dropna()
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
        
        if category in categories:
            categories[category][base]['weighted_sum'] += strength * weight
            categories[category][base]['total_weight'] += weight
            categories[category][quote]['weighted_sum'] += (-strength) * weight
            categories[category][quote]['total_weight'] += weight
    
    raw_values = {}
    for ent, v in scores_acc.items():
        raw_values[ent] = v['weighted_sum'] / v['total_weight'] if v['total_weight'] > 0 else 0.0
    
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
            if len(s) < 2 or s.std() == 0:
                zc = np.zeros_like(s.values)
            else:
                zc = zscore(s.values, nan_policy='omit')
            zc = np.clip(np.nan_to_num(zc), -3, 3)
            scaled_c = 5 + (zc / 6) * 10
            scaled_c = np.clip(scaled_c, 0, 10)
            category_frames[cat] = pd.DataFrame({'score_smoothed': np.round(scaled_c, 2)}, index=s.index).sort_values(by='score_smoothed', ascending=False)

    return df_raw, category_frames

# ----------------------------
# STREAMLIT UI
# ----------------------------
st.set_page_config(
    page_title="Strength Meter PRO",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS pour design aquarelle vibrant (thermomètres segmentés)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');
    
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
        font-family: 'Roboto', sans-serif;
    }
    
    .main-header {
        text-align: center;
        padding: 1.5rem 0;
        background: linear-gradient(90deg, #ef4444 0%, #fbbf24 20%, #bef264 40%, #4ade80 60%, #22c55e 80%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
    }
    
    .subtitle {
        text-align: center;
        color: #475569;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    .gauge-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 1.5rem;
        margin: 2rem 0;
    }
    
    .gauge-card {
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(12px);
        border-radius: 20px;
        padding: 1.25rem;
        border: 1px solid rgba(203, 213, 225, 0.3);
        transition: all 0.3s ease;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    .gauge-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.15);
    }
    
    .gauge-label {
        font-size: 1.2rem;
        font-weight: 700;
        color: #334155;
        margin-bottom: 1rem;
    }
    
    .thermometer {
        width: 30px;
        height: 220px;
        margin: 0 auto 1rem;
        position: relative;
        background: linear-gradient(to top, #ef4444, #fb923c, #fde047, #bef264, #22c55e);
        border-radius: 15px;
        box-shadow: 0 0 15px rgba(0, 0, 0, 0.1), inset 0 2px 5px rgba(255, 255, 255, 0.5);
        overflow: hidden;
        filter: blur(0.5px); /* Effet aquarelle doux */
        opacity: 0.95;
    }
    
    .thermo-fill {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        background: linear-gradient(to top, #ef4444, #fb923c, #fde047, #bef264, #22c55e);
        transition: height 0.8s ease;
        border-radius: 0 0 15px 15px;
    }
    
    .thermo-bulb {
        position: absolute;
        bottom: -20px;
        left: 50%;
        transform: translateX(-50%);
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background: radial-gradient(circle, #ef4444 0%, #dc2626 100%);
        box-shadow: 0 0 20px rgba(239, 68, 68, 0.6);
        transition: background 0.8s ease;
    }
    
    .score-display {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1e293b;
    }
    
    .strength-label {
        font-size: 0.9rem;
        font-weight: 600;
        color: #475569;
        text-transform: uppercase;
    }
    
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 2.5rem 0 1.5rem;
        padding: 1rem;
        background: rgba(255, 255, 255, 0.6);
        border-radius: 12px;
        border-left: 4px solid #3b82f6;
    }
    
    .section-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #1e293b;
    }
    
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
        color: white;
        font-weight: 600;
        border: none;
        border-radius: 12px;
        padding: 0.8rem;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        box-shadow: 0 5px 15px rgba(59, 130, 246, 0.4);
    }
    
    .info-box {
        background: rgba(255, 255, 255, 0.7);
        border-left: 4px solid #3b82f6;
        padding: 1rem;
        border-radius: 8px;
        color: #334155;
        margin: 1rem 0;
    }
    
    @media (max-width: 768px) {
        .gauge-grid { grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); }
        .thermometer { width: 25px; height: 180px; }
        .thermo-bulb { width: 40px; height: 40px; bottom: -15px; }
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<h1 class="main-header">🌡️ Strength Meter PRO</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Thermomètres Aquarelle Vibrants - Analyse de Force</p>', unsafe_allow_html=True)
st.markdown("""
<div class="info-box">
    <strong>🎯 Méthodologie :</strong> ATR normalisé + Z-score |
    <strong>📊 Assets :</strong> Paires FX, Métaux & Indices
</div>
""", unsafe_allow_html=True)

# Bouton
if st.button("🚀 Lancer l'Analyse", use_container_width=True):
    with st.spinner("⏳ Calcul en cours..."):
        df_entities, category_frames = compute_strength(CONFIG)
    
    if df_entities.empty:
        st.error("❌ Aucune donnée disponible.")
    else:
        # Sections par catégorie
        for cat, df_cat in category_frames.items():
            if not df_cat.empty:
                st.markdown(f"""
                <div class="section-header">
                    <span style="font-size: 1.5rem;">{'💱' if cat == 'FX' else ('🥇' if cat == 'METAL' else '📈')}</span>
                    <h2 class="section-title">{cat} - Thermomètres</h2>
                </div>
                """, unsafe_allow_html=True)
                
                gauge_html = '<div class="gauge-grid">'
                for ent in df_cat.index:
                    score = float(df_cat.loc[ent, 'score_smoothed'])
                    height_pct = max(min(score / 10.0, 1.0), 0.0) * 100
                    bulb_color = '#ef4444' if score < 4 else ('#fde047' if score < 7 else '#22c55e')
                    
                    gauge_html += f"""
                    <div class="gauge-card">
                        <div class="gauge-label">{ent}</div>
                        <div class="thermometer">
                            <div class="thermo-fill" style="height: {height_pct}%;"></div>
                        </div>
                        <div class="thermo-bulb" style="background: radial-gradient(circle, {bulb_color} 0%, darken({bulb_color}, 20%) 100%); box-shadow: 0 0 20px rgba({int(bulb_color[1:3],16)}, {int(bulb_color[3:5],16)}, {int(bulb_color[5:7],16)}, 0.6);"></div>
                        <div class="score-display">{score:.1f}</div>
                        <div class="strength-label">{get_strength_label(score)}</div>
                    </div>
                    """
                gauge_html += '</div>'
                st.markdown(gauge_html, unsafe_allow_html=True)
        
        # Graphique Plotly optionnel
        st.markdown("""
        <div class="section-header">
            <span style="font-size: 1.5rem;">📊</span>
            <h2 class="section-title">Comparaison Globale</h2>
        </div>
        """, unsafe_allow_html=True)
        fig = px.bar(df_entities.reset_index(), x='index', y='score_smoothed', 
                     color='score_smoothed', color_continuous_scale='RdYlGn',
                     labels={'index': 'Actif', 'score_smoothed': 'Score'})
        st.plotly_chart(fig, use_container_width=True)

else:
    st.markdown("""
    <div class="info-box">
        👆 Cliquez pour lancer l'analyse et voir les thermomètres vibrants !
    </div>
    """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
<p style='text-align: center; color: #475569; font-size: 0.9rem;'>
    Made with 💜 | Données: Yahoo Finance | Design Aquarelle Vibrant
</p>
""", unsafe_allow_html=True)

def get_strength_label(score):
    if score <= 2: return "Très Faible"
    elif score <= 4: return "Faible"
    elif score <= 6: return "Neutre"
    elif score <= 8: return "Fort"
    else: return "Très Fort"
