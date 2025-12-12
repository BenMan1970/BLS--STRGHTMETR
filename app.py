import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore

# ------------------------------------------------------------
# 1. CONFIGURATION & STYLES CSS
# ------------------------------------------------------------
st.set_page_config(page_title="Market Strength Visualizer", layout="wide")

# CSS pour reproduire exactement le style visuel demandé (Barres segmentées + Curseur)
st.markdown("""
<style>
    /* Fond global sombre style 'Trading' */
    .stApp {
        background-color: #0e1117;
    }
    
    /* Conteneur de la ligne d'actif */
    .asset-row {
        display: flex;
        align-items: center;
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 10px 15px;
        margin-bottom: 8px;
        transition: transform 0.2s;
    }
    .asset-row:hover {
        border-color: #58a6ff;
        transform: translateX(5px);
    }

    /* Texte du Symbole */
    .symbol-text {
        font-family: 'Roboto Mono', monospace;
        font-weight: 700;
        font-size: 16px;
        color: #e6edf3;
        width: 80px;
    }

    /* Conteneur de la jauge */
    .gauge-container {
        position: relative;
        width: 100%;
        height: 40px; /* Espace pour les barres + le curseur en dessous */
        display: flex;
        flex-direction: column;
        justify-content: center;
        margin: 0 15px;
    }

    /* Les barres segmentées */
    .segments-wrapper {
        display: flex;
        gap: 4px; /* Espace entre les blocs */
        height: 20px;
        width: 100%;
    }
    
    .segment {
        flex: 1;
        border-radius: 4px;
        height: 100%;
    }

    /* Le curseur triangle */
    .cursor-marker {
        position: absolute;
        top: 24px; /* Juste sous la barre */
        width: 0; 
        height: 0; 
        border-left: 6px solid transparent;
        border-right: 6px solid transparent;
        border-bottom: 8px solid #ffffff; /* Couleur du curseur */
        transform: translateX(-50%);
        transition: left 0.5s ease-out;
    }

    /* Score numérique */
    .score-badge {
        background-color: #21262d;
        color: #fff;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-family: monospace;
        min-width: 50px;
        text-align: center;
        border: 1px solid #30363d;
    }
</style>
""", unsafe_allow_html=True)

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
    'atr_period': 14, 'atr_floor_pct': 1e-4, 'smoothing_span': 3, 'category_mode': True
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
    # Téléchargement des données
    all_tickers = list(tickers_cfg.keys())
    data = yf.download(all_tickers, period=config['period'], interval=config['interval'], group_by='ticker', progress=False)

    entities = set()
    for t, v in tickers_cfg.items():
        entities.add(v[1]); entities.add(v[2])

    scores_acc = {e: {'weighted_sum': 0, 'total_weight': 0} for e in entities}

    for ticker, info in tickers_cfg.items():
        weight, base, quote, _ = info
        if ticker not in data.columns.get_level_values(0): continue
        
        df = data[ticker].dropna()
        if len(df) < max(config['atr_period'] + 2, config['lookback_days'] + 2): continue

        close = df['Close']
        price_now = close.iloc[-1]
        price_past = close.shift(config['lookback_days']).iloc[-1]
        
        if pd.isna(price_now) or pd.isna(price_past) or price_past == 0: continue

        # Performance relative ajustée par la volatilité (ATR)
        raw_move_pct = (price_now - price_past) / price_past
        atr = calculate_atr(df, config['atr_period']).iloc[-1]
        atr_pct = max(atr / price_now, config['atr_floor_pct']) if price_now != 0 else config['atr_floor_pct']
        
        strength = raw_move_pct / atr_pct

        scores_acc[base]['weighted_sum'] += strength * weight
        scores_acc[base]['total_weight'] += weight
        scores_acc[quote]['weighted_sum'] -= strength * weight
        scores_acc[quote]['total_weight'] += weight

    raw_values = {k: v['weighted_sum'] / v['total_weight'] if v['total_weight'] > 0 else 0 for k, v in scores_acc.items()}
    
    # Normalisation Z-Score -> 0 à 10
    df_raw = pd.DataFrame.from_dict(raw_values, orient='index', columns=['raw'])
    vals = df_raw['raw'].values
    z = zscore(vals, nan_policy='omit') if np.std(vals) > 0 else np.zeros_like(vals)
    z = np.clip(np.nan_to_num(z), -3, 3) # Cap à +/- 3 écarts types
    
    # Transformation en échelle 0-10
    df_raw['score'] = np.clip(5 + (z / 6) * 10, 0, 10)
    df_raw['score_smoothed'] = df_raw['score'].ewm(span=config['smoothing_span']).mean()
    
    return df_raw.sort_values(by='score_smoothed', ascending=False)

# ------------------------------------------------------------
# 3. MOTEUR VISUEL HTML (SEGMENTED BAR)
# ------------------------------------------------------------
def create_segmented_bar(score):
    """
    Génère le HTML pour une barre segmentée de 10 blocs + curseur.
    Score attendu : float entre 0 et 10.
    """
    # Palette de 10 couleurs (Rouge -> Orange -> Jaune -> Vert)
    colors = [
        "#ff4d4d", "#ff7340", "#ff9933", "#ffbf26", 
        "#ffe61a", "#d9f22e", "#b2f043", "#8ceb57", 
        "#66e66c", "#40e080"
    ]
    
    score = max(0, min(10, score)) # Clamp
    
    # Génération des 10 blocs
    segments_html = ""
    for i in range(10):
        color = colors[i]
        # Logique d'allumage : 
        # Si le score est supérieur à l'index du bloc, il est allumé (opacité 1.0)
        # Sinon il est éteint (opacité 0.2)
        # On peut affiner : si score = 5.5, le bloc 6 (index 5) est à moitié allumé ? 
        # Pour simplifier et rester "punchy" visuellement, on utilise un seuil ou opacité pleine.
        
        opacity = "1.0" if score >= i + 0.2 else "0.2"
        # Petit effet de brillance si le bloc est actif
        box_shadow = f"0 0 8px {color}66" if opacity == "1.0" else "none"
        
        segments_html += f"""
        <div class="segment" style="background-color: {color}; opacity: {opacity}; box-shadow: {box_shadow};"></div>
        """
    
    # Position du curseur en pourcentage (0 à 100%)
    cursor_pos = (score / 10) * 100
    
    html = f"""
    <div class="gauge-container">
        <div class="segments-wrapper">
            {segments_html}
        </div>
        <div class="cursor-marker" style="left: {cursor_pos}%; border-bottom-color: #fff;"></div>
    </div>
    """
    return html

# ------------------------------------------------------------
# 4. INTERFACE STREAMLIT
# ------------------------------------------------------------

st.title("⚡ Strength Meter PRO")
st.markdown("Analyse visuelle de la force relative des devises et indices.")

if st.button("🔄 Actualiser les données", type="primary"):
    with st.spinner("Analyse du marché en cours..."):
        try:
            df_res = compute_strength(CONFIG)
            
            # --- SECTION RÉSUMÉ ---
            strongest = df_res.index[0]
            weakest = df_res.index[-1]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.info(f"🚀 Plus Fort: **{strongest}**")
            with col2:
                st.error(f"💀 Plus Faible: **{weakest}**")
            with col3:
                st.success(f"💡 Idée: **Long {strongest} / Short {weakest}**")
            
            st.divider()
            
            # --- LISTE VISUELLE ---
            # On n'utilise pas st.dataframe, mais une boucle de colonnes pour un contrôle total du design
            
            for asset, row in df_res.iterrows():
                score_val = row['score_smoothed']
                
                # Layout en 3 colonnes : Nom (petit) | Jauge (large) | Score (petit)
                c_name, c_gauge, c_score = st.columns([1.5, 6, 1])
                
                with c_name:
                    st.markdown(f"<div style='margin-top: 18px; font-weight:bold; font-size:18px;'>{asset}</div>", unsafe_allow_html=True)
                
                with c_gauge:
                    # Injection du HTML généré
                    st.markdown(create_segmented_bar(score_val), unsafe_allow_html=True)
                
                with c_score:
                    color_score = "#40e080" if score_val > 7 else ("#ff4d4d" if score_val < 3 else "#e6edf3")
                    st.markdown(f"""
                        <div style='margin-top: 15px; text-align:right; font-family:monospace; font-size:18px; color:{color_score};'>
                        {score_val:.2f}
                        </div>
                    """, unsafe_allow_html=True)
                
                # Petit séparateur discret
                st.markdown("<hr style='margin: 5px 0; border: 0; border-top: 1px solid #30363d;'>", unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Erreur de calcul : {e}")

else:
    st.info("Cliquez sur le bouton pour lancer l'analyse.")

# Footer discret
st.markdown("<br><div style='text-align:center; color:#555; font-size:12px;'>Data powered by Yahoo Finance | ATR Volatility Adjusted</div>", unsafe_allow_html=True)
