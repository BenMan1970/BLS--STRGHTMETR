# app.py — Strength Meter PRO (Vue Gauge/Thermomètre)
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore

# ----------------------------
# CONFIG - 28 Paires Forex + Métaux + Indices
# ----------------------------
CONFIG = {
    'tickers': {
        # 28 PAIRES FOREX MAJEURES
        'EURUSD=X': [20.0, 'EUR', 'USD', 'FX'],
        'GBPUSD=X': [18.0, 'GBP', 'USD', 'FX'],
        'USDJPY=X': [17.0, 'USD', 'JPY', 'FX'],
        'USDCHF=X': [15.0, 'USD', 'CHF', 'FX'],
        'AUDUSD=X': [14.0, 'AUD', 'USD', 'FX'],
        'USDCAD=X': [13.0, 'USD', 'CAD', 'FX'],
        'NZDUSD=X': [12.0, 'NZD', 'USD', 'FX'],
        'EURGBP=X': [11.0, 'EUR', 'GBP', 'FX'],
        'EURJPY=X': [10.0, 'EUR', 'JPY', 'FX'],
        'EURCHF=X': [9.0, 'EUR', 'CHF', 'FX'],
        'EURAUD=X': [8.0, 'EUR', 'AUD', 'FX'],
        'EURCAD=X': [7.0, 'EUR', 'CAD', 'FX'],
        'EURNZD=X': [6.0, 'EUR', 'NZD', 'FX'],
        'GBPJPY=X': [9.0, 'GBP', 'JPY', 'FX'],
        'GBPCHF=X': [8.0, 'GBP', 'CHF', 'FX'],
        'GBPAUD=X': [7.0, 'GBP', 'AUD', 'FX'],
        'GBPCAD=X': [6.0, 'GBP', 'CAD', 'FX'],
        'GBPNZD=X': [5.0, 'GBP', 'NZD', 'FX'],
        'AUDJPY=X': [7.0, 'AUD', 'JPY', 'FX'],
        'AUDCHF=X': [6.0, 'AUD', 'CHF', 'FX'],
        'AUDCAD=X': [5.0, 'AUD', 'CAD', 'FX'],
        'AUDNZD=X': [4.0, 'AUD', 'NZD', 'FX'],
        'NZDJPY=X': [5.0, 'NZD', 'JPY', 'FX'],
        'NZDCHF=X': [4.0, 'NZD', 'CHF', 'FX'],
        'NZDCAD=X': [3.0, 'NZD', 'CAD', 'FX'],
        'CADJPY=X': [5.0, 'CAD', 'JPY', 'FX'],
        'CADCHF=X': [4.0, 'CAD', 'CHF', 'FX'],
        'CHFJPY=X': [4.0, 'CHF', 'JPY', 'FX'],
        # MÉTAUX
        'GC=F': [15.0, 'XAU', 'USD', 'METAL'],
        'PL=F': [8.0, 'XPT', 'USD', 'METAL'],
        # INDICES
        '^DJI': [12.0, 'US30', 'USD', 'INDEX'],
        '^IXIC': [12.0, 'NAS100', 'USD', 'INDEX'],
        '^GSPC': [15.0, 'SPX500', 'USD', 'INDEX'],
    },
    'period': '60d',
    'interval': '1d',
    'lookback_days': 3,
    'atr_period': 14,
    'atr_floor_pct': 1e-4,
    'smoothing_span': 3,
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
# Palette de couleurs
# ----------------------------
def get_color_from_score(score):
    if score <= 2:
        return '#dc2626'  # Rouge fort
    elif score <= 4:
        return '#f97316'  # Orange
    elif score <= 6:
        return '#eab308'  # Jaune
    elif score <= 8:
        return '#22c55e'  # Vert
    else:
        return '#06b6d4'  # Cyan

def get_strength_label(score):
    if score <= 2:
        return "Très Faible"
    elif score <= 4:
        return "Faible"
    elif score <= 6:
        return "Neutre"
    elif score <= 8:
        return "Fort"
    else:
        return "Très Fort"

# ----------------------------
# CORE: compute_strength (avec cache pour perf)
# ----------------------------
@st.cache_data(ttl=300)  # Cache 5 min pour données live
def compute_strength(config=CONFIG):
    tickers_cfg = config['tickers']
    lookback = config['lookback_days']
    atr_period = config['atr_period']
    atr_floor_pct = config['atr_floor_pct']
    all_tickers = list(tickers_cfg.keys())
    try:
        data = yf.download(all_tickers, period=config['period'], interval=config['interval'],
                           progress=False, threads=False)  # threads=False pour Streamlit
    except Exception as e:
        st.error(f"❌ Erreur téléchargement yfinance: {e}")
        return pd.DataFrame()
    
    entities = set()
    for v in tickers_cfg.values():
        entities.add(v[1])
        entities.add(v[2])
    
    scores_acc = {e: {'weighted_sum': 0.0, 'total_weight': 0.0} for e in entities}
    
    for ticker, info in tickers_cfg.items():
        weight, base, quote, category = info
        if ticker not in data.columns.get_level_values(1):  # Niveau 1 = tickers maintenant
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
    return df_raw

# ----------------------------
# STREAMLIT UI
# ----------------------------
st.set_page_config(
    page_title="Strength Meter PRO",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS Moderne avec Gauges (simplifié un peu)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    [data-testid="stAppViewContainer"] { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); font-family: 'Inter', sans-serif; }
    .main-header { text-align: center; padding: 1.5rem 0; background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.5rem; font-weight: 700; }
    .subtitle { text-align: center; color: #94a3b8; font-size: 1rem; margin-bottom: 2rem; }
    .gauge-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1.5rem; margin: 2rem 0; }
    .gauge-card { background: rgba(30, 41, 59, 0.6); backdrop-filter: blur(10px); border-radius: 16px; padding: 1.25rem; border: 1px solid rgba(148, 163, 184, 0.1); transition: all 0.3s ease; text-align: center; }
    .gauge-card:hover { transform: translateY(-5px); border-color: rgba(148, 163, 184, 0.3); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5); }
    .gauge-label { font-size: 1.1rem; font-weight: 700; color: #e2e8f0; margin-bottom: 1rem; letter-spacing: 0.5px; }
    .thermometer { width: 60px; height: 200px; margin: 0 auto 1rem; position: relative; background: rgba(15, 23, 42, 0.8); border-radius: 30px; padding: 8px; box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.4); }
    .thermo-fill { position: absolute; bottom: 8px; left: 8px; right: 8px; border-radius: 22px; transition: all 0.8s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 0 20px currentColor; }
    .thermo-bulb { position: absolute; bottom: -15px; left: 50%; transform: translateX(-50%); width: 50px; height: 50px; border-radius: 50%; transition: all 0.8s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 0 25px currentColor; }
    .score-display { font-size: 2rem; font-weight: 700; margin: 0.5rem 0; }
    .strength-label { font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; opacity: 0.9; }
    .section-header { display: flex; align-items: center; justify-content: center; gap: 0.75rem; margin: 2.5rem 0 1.5rem 0; padding: 1rem; background: rgba(51, 65, 85, 0.3); border-radius: 12px; border-left: 4px solid #3b82f6; }
    .section-title { font-size: 1.5rem; font-weight: 700; color: #f1f5f9; margin: 0; }
    .stButton > button { width: 100%; background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); color: white; font-weight: 600; font-size: 1.1rem; padding: 0.8rem 2rem; border: none; border-radius: 12px; transition: all 0.3s ease; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(59, 130, 246, 0.4); }
    .info-box { background: rgba(59, 130, 246, 0.1); border-left: 4px solid #3b82f6; padding: 1rem 1.25rem; border-radius: 8px; color: #bfdbfe; margin: 1rem 0; }
    .compact-table { width: 100%; border-collapse: collapse; margin: 1rem 0; background: rgba(30, 41, 59, 0.4); border-radius: 12px; overflow: hidden; }
    .compact-table th { background: rgba(51, 65, 85, 0.6); color: #94a3b8; padding: 0.75rem; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; }
    .compact-table td { padding: 0.6rem 0.75rem; color: #e2e8f0; border-bottom: 1px solid rgba(148, 163, 184, 0.1); }
    .compact-table tr:hover { background: rgba(51, 65, 85, 0.3); }
    @media (max-width: 768px) { .gauge-grid { grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); } .thermometer { width: 50px; height: 160px; } .thermo-bulb { width: 40px; height: 40px; } }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<h1 class="main-header">🌡️ Strength Meter PRO</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Vue Thermomètre - Analyse de force instantanée</p>', unsafe_allow_html=True)
st.markdown("""
<div class="info-box">
    <strong>🎯 Méthodologie :</strong> ATR normalisé + Z-score |
    <strong>📊 33 Assets :</strong> 28 paires FX + 2 métaux + 3 indices
</div>
""", unsafe_allow_html=True)

# Bouton de calcul
if st.button("🚀 LANCER L'ANALYSE", use_container_width=True):
    with st.spinner("⏳ Calcul en cours..."):
        df_entities = compute_strength(CONFIG)
    if df_entities.empty:
        st.error("❌ Aucune donnée calculée.")
    else:
        # VUE PRINCIPALE: GAUGES THERMOMÈTRES
        st.markdown("""
        <div class="section-header">
            <span style="font-size: 1.5rem;">🌡️</span>
            <h2 class="section-title">Thermomètres de Force</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Création des gauges en HTML
        gauge_html = '<div class="gauge-grid">'
        for ent in df_entities.index:
            score = float(df_entities.loc[ent, 'score_smoothed'])
            height_pct = max(min(score / 10.0, 1.0), 0.0) * 100
            color = get_color_from_score(score)
            label = get_strength_label(score)
            gauge_html += f"""
            <div class="gauge-card">
                <div class="gauge-label">{ent}</div>
                <div class="thermometer">
                    <div class="thermo-fill" style="height: {height_pct}%; background: {color}; color: {color};"></div>
                    <div class="thermo-bulb" style="background: {color}; color: {color};"></div>
                </div>
                <div class="score-display" style="color: {color};">{score:.1f}</div>
                <div class="strength-label" style="color: {color};">{label}</div>
            </div>
            """
        gauge_html += '</div>'
        st.markdown(gauge_html, unsafe_allow_html=True)
        
        # SECTION PAIRES (Compact)
        st.markdown("""
        <div class="section-header">
            <span style="font-size: 1.5rem;">💹</span>
            <h2 class="section-title">Analyse Détaillée des Paires</h2>
        </div>
        """, unsafe_allow_html=True)
        
        pairs_list = []
        for ticker, info in CONFIG['tickers'].items():
            weight, base, quote, category = info
            if base in df_entities.index and quote in df_entities.index:
                base_s = float(df_entities.loc[base, 'score_smoothed'])
                quote_s = float(df_entities.loc[quote, 'score_smoothed'])
                diff = base_s - quote_s
                pair_score = (diff + 10.0) / 20.0 * 10.0
                pair_score = float(np.clip(pair_score, 0.0, 10.0))
            else:
                pair_score = 5.0
            pairs_list.append({
                'Paire': ticker.replace('=X', '').replace('^', '').replace('=F', ''),
                'Base': base,
                'Quote': quote,
                'Score': round(pair_score, 2),
                'Force': get_strength_label(pair_score),
                'Catégorie': category
            })
        df_pairs = pd.DataFrame(pairs_list).sort_values(by='Score', ascending=False).reset_index(drop=True)
        
        # Affichage en tableau compact avec style
        table_html = '<table class="compact-table"><thead><tr><th>Paire</th><th>Base</th><th>Quote</th><th>Score</th><th>Force</th><th>Catégorie</th></tr></thead><tbody>'
        for _, row in df_pairs.iterrows():
            color = get_color_from_score(row['Score'])
            icon = '💱' if row['Catégorie'] == 'FX' else ('🥇' if row['Catégorie'] == 'METAL' else '📈')
            table_html += f"""
            <tr>
                <td style="font-weight: 600;">{row['Paire']}</td>
                <td>{row['Base']}</td>
                <td>{row['Quote']}</td>
                <td style="color: {color}; font-weight: 700; font-size: 1.1rem;">{row['Score']:.2f}</td>
                <td style="color: {color}; font-weight: 600;">{row['Force']}</td>
                <td>{icon} {row['Catégorie']}</td>
            </tr>
            """
        table_html += '</tbody></table>'
        st.markdown(table_html, unsafe_allow_html=True)
        
        # Export CSV
        st.markdown("---")
        out_entities = df_entities.reset_index().rename(columns={'index': 'entity'})
        csv_buf = "== ENTITÉS ==\n" + out_entities.to_csv(index=False) + "\n\n== PAIRES ==\n" + df_pairs.to_csv(index=False)
        st.download_button(
            "📥 Télécharger les résultats (CSV)",
            csv_buf.encode('utf-8'),
            file_name='strength_analysis.csv',
            mime='text/csv',
            use_container_width=True
        )
else:
    st.markdown("""
    <div class="info-box">
        👆 Cliquez sur le bouton pour voir les thermomètres de force en temps réel
    </div>
    """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
<p style='text-align: center; color: #64748b; font-size: 0.9rem;'>
    Made with 💜 | Données: Yahoo Finance
</p>
""", unsafe_allow_html=True)
