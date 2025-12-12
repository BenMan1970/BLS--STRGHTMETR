import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore

# ------------------------------------------------------------
# 1. CONFIGURATION & STYLE (CSS VISUEL)
# ------------------------------------------------------------
st.set_page_config(page_title="Strength Meter PRO", layout="wide", page_icon="📈")

# CSS : C'est ici que la magie visuelle opère (Barres, alignement, couleurs)
st.markdown("""
<style>
    /* Fond général sombre */
    .stApp { background-color: #0e1117; }
    
    /* Conteneur de la jauge */
    .gauge-container {
        display: flex;
        flex-direction: row; /* Force l'alignement horizontal */
        align-items: center;
        gap: 4px; /* Espace entre les segments */
        height: 24px;
        width: 100%;
        padding-top: 5px;
    }
    
    /* Les segments (rectangles colorés) */
    .segment {
        flex: 1; /* Prend toute la largeur dispo */
        height: 100%;
        border-radius: 3px;
        transition: all 0.3s ease;
    }

    /* Texte des actifs (Symboles) */
    .ticker-text {
        font-family: 'Arial', sans-serif;
        font-weight: 900;
        font-size: 18px;
        color: #f0f2f6;
        display: flex;
        align-items: center;
        height: 100%;
    }

    /* Score à droite */
    .score-text {
        font-family: 'Courier New', monospace;
        font-weight: bold;
        font-size: 18px;
        text-align: right;
    }
    
    /* Ligne de séparation fine */
    hr { margin: 0.5em 0; border-color: #30363d; opacity: 0.4; }
</style>
""", unsafe_allow_html=True)

# Configuration des actifs
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
    'period': '60d', 'interval': '1d', 'lookback_days': 3,
    'atr_period': 14, 'atr_floor_pct': 1e-4, 'smoothing_span': 3
}

# ------------------------------------------------------------
# 2. FONCTIONS DE CALCUL (MOTEUR)
# ------------------------------------------------------------
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

def compute_strength(config=CONFIG):
    tickers_cfg = config['tickers']
    all_tickers = list(tickers_cfg.keys())
    
    # Téléchargement optimisé
    data = yf.download(all_tickers, period=config['period'], interval=config['interval'], group_by='ticker', progress=False)

    entities = set()
    for t, v in tickers_cfg.items():
        entities.add(v[1]); entities.add(v[2])

    scores_acc = {e: {'weighted_sum': 0, 'total_weight': 0} for e in entities}

    for ticker, info in tickers_cfg.items():
        weight, base, quote, _ = info
        # Gestion des cas où le ticker n'est pas trouvé
        if ticker not in data.columns.get_level_values(0): continue
        
        df = data[ticker].dropna()
        if len(df) < 20: continue

        close = df['Close']
        price_now = close.iloc[-1]
        price_past = close.shift(config['lookback_days']).iloc[-1]
        
        if pd.isna(price_now) or pd.isna(price_past) or price_past == 0: continue

        raw_move_pct = (price_now - price_past) / price_past
        atr = calculate_atr(df, config['atr_period']).iloc[-1]
        atr_pct = max(atr / price_now, config['atr_floor_pct']) if price_now != 0 else config['atr_floor_pct']
        
        strength = raw_move_pct / atr_pct

        scores_acc[base]['weighted_sum'] += strength * weight
        scores_acc[base]['total_weight'] += weight
        scores_acc[quote]['weighted_sum'] -= strength * weight
        scores_acc[quote]['total_weight'] += weight

    raw_values = {k: v['weighted_sum'] / v['total_weight'] if v['total_weight'] > 0 else 0 for k, v in scores_acc.items()}
    
    # Normalisation
    df_raw = pd.DataFrame.from_dict(raw_values, orient='index', columns=['raw'])
    vals = df_raw['raw'].values
    z = zscore(vals, nan_policy='omit') if np.std(vals) > 0 else np.zeros_like(vals)
    z = np.clip(np.nan_to_num(z), -3, 3) 
    
    # Score final 0-10
    df_raw['score'] = np.clip(5 + (z / 6) * 10, 0, 10)
    df_raw['score_smoothed'] = df_raw['score'].ewm(span=config['smoothing_span']).mean()
    
    return df_raw.sort_values(by='score_smoothed', ascending=False)

# ------------------------------------------------------------
# 3. GÉNÉRATEUR HTML DE LA JAUGE (CORRIGÉ)
# ------------------------------------------------------------
def get_gauge_html(score):
    # Palette Dégradé: Rouge -> Orange -> Jaune -> Vert
    colors = [
        "#ff3333", "#ff6633", "#ff9933", "#ffcc33", 
        "#ffff33", "#ccff33", "#99ff33", "#66ff33", 
        "#33ff33", "#00ff33"
    ]
    
    # Clamp score
    score = max(0, min(10, score))
    
    segments = ""
    for i in range(10):
        color = colors[i]
        # Si le score dépasse cet index, on allume, sinon on éteint
        opacity = "1.0" if score >= (i + 0.5) else "0.15"
        # Ajout d'une ombre ("Glow") si allumé pour effet néon
        shadow = f"0 0 8px {color}" if opacity == "1.0" else "none"
        
        segments += f'<div class="segment" style="background:{color}; opacity:{opacity}; box-shadow:{shadow};"></div>'
    
    # Curseur triangle sous la barre
    cursor_pos = (score / 10) * 100
    cursor_html = f"""
    <div style="position:absolute; bottom:-6px; left:{cursor_pos}%; transform:translateX(-50%); width:0; height:0; border-left:6px solid transparent; border-right:6px solid transparent; border-bottom:8px solid #fff;"></div>
    """
    
    return f"""
    <div style="position:relative; width:100%;">
        <div class="gauge-container">{segments}</div>
        {cursor_html}
    </div>
    """

# ------------------------------------------------------------
# 4. AFFICHAGE STREAMLIT
# ------------------------------------------------------------

st.title("⚡ MARKET STRENGTH METER")

if st.button("🔄 ACTUALISER LE MARCHÉ", type="primary"):
    with st.spinner("Analyse des flux en cours..."):
        try:
            df = compute_strength()
            
            # --- HEADER DASHBOARD ---
            strongest = df.index[0]
            weakest = df.index[-1]
            
            col_dash1, col_dash2, col_dash3 = st.columns(3)
            col_dash1.success(f"🚀 Leader: {strongest}")
            col_dash2.error(f"💀 Laggard: {weakest}")
            col_dash3.info(f"💡 Trade: Long {strongest} / Short {weakest}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- TABLEAU VISUEL (LA BOUCLE MAGIQUE) ---
            # En-têtes
            h1, h2, h3 = st.columns([1, 6, 1])
            h1.markdown("### Asset")
            h2.markdown("### Power")
            h3.markdown("### Score")
            st.divider()

            # Boucle d'affichage ligne par ligne
            for asset, row in df.iterrows():
                score = row['score_smoothed']
                
                # Colonnes : Nom | Jauge | Score
                c1, c2, c3 = st.columns([1, 6, 1])
                
                with c1:
                    # Affichage du Nom
                    st.markdown(f'<div class="ticker-text">{asset}</div>', unsafe_allow_html=True)
                
                with c2:
                    # Affichage de la Jauge (C'est ICI que le HTML est rendu)
                    html_bar = get_gauge_html(score)
                    st.markdown(html_bar, unsafe_allow_html=True)
                
                with c3:
                    # Affichage du Score coloré
                    color = "#00ff33" if score > 7 else ("#ff3333" if score < 3 else "#ffffff")
                    st.markdown(f'<div class="score-text" style="color:{color};">{score:.2f}</div>', unsafe_allow_html=True)
                
                # Petit espace entre les lignes
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                st.markdown("<hr>", unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Erreur: {e}")
else:
    st.info("Cliquez sur Actualiser pour charger les données.")
