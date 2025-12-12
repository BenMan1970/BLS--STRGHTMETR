import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore

# ------------------------------------------------------------
# 1. CONFIGURATION VISUELLE (CSS)
# ------------------------------------------------------------
st.set_page_config(page_title="Market Heatmap", layout="wide")

st.markdown("""
<style>
    /* Fond sombre général */
    .stApp { background-color: #0e1117; }

    /* Conteneur principal Flexbox : Aligne les boîtes automatiquement */
    .heatmap-container {
        display: flex;
        flex-wrap: wrap;       /* Permet de passer à la ligne si pas de place */
        gap: 6px;              /* Petit espace entre les tuiles */
        justify-content: flex-start;
        padding-bottom: 20px;
    }

    /* LA TUILE (Carte rectangulaire) */
    .market-tile {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        width: 110px;          /* Largeur fixe compacte */
        height: 60px;          /* Hauteur fixe compacte */
        border-radius: 6px;
        color: white;
        box-shadow: 0 2px 5px rgba(0,0,0,0.4);
        border: 1px solid rgba(255,255,255,0.05);
        transition: transform 0.1s;
    }
    
    .market-tile:hover {
        transform: scale(1.05);
        border-color: rgba(255,255,255,0.5);
        cursor: pointer;
    }

    /* Texte du Symbole (ex: EURUSD) */
    .tile-symbol {
        font-family: 'Arial', sans-serif;
        font-weight: 800;
        font-size: 13px;
        margin-bottom: 2px;
        text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    }
    
    /* Texte du Score (ex: 8.5) */
    .tile-score {
        font-family: 'Courier New', monospace;
        font-weight: bold;
        font-size: 14px;
        background-color: rgba(0,0,0,0.2); /* Petit fond sombre sous le score */
        padding: 0 6px;
        border-radius: 4px;
    }

    /* Titres de section */
    .section-title {
        color: #8b949e;
        font-size: 15px;
        font-weight: bold;
        margin: 15px 0 8px 0;
        border-bottom: 1px solid #30363d;
        display: inline-block;
        padding-bottom: 2px;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 2. LISTE DES ACTIFS
# ------------------------------------------------------------
CONFIG = {
    'tickers': [
        # --- FOREX (28 Paires Majeures & Mineures) ---
        'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'AUDUSD=X', 'USDCAD=X', 'NZDUSD=X',
        'EURGBP=X', 'EURJPY=X', 'EURCHF=X', 'EURAUD=X', 'EURCAD=X', 'EURNZD=X',
        'GBPJPY=X', 'GBPCHF=X', 'GBPAUD=X', 'GBPCAD=X', 'GBPNZD=X',
        'AUDJPY=X', 'AUDCAD=X', 'AUDNZD=X', 'AUDCHF=X',
        'CADJPY=X', 'CADCHF=X', 'NZDJPY=X', 'NZDCHF=X', 'CHFJPY=X',
        
        # --- INDICES ---
        '^DJI', '^GSPC', '^IXIC', '^FCHI', '^GDAXI',
        
        # --- MATIÈRES PREMIÈRES ---
        'GC=F', 'CL=F', 'SI=F', 'HG=F'
    ],
    'period': '60d', 'interval': '1d', 'lookback_days': 3, 'atr_period': 14
}

# ------------------------------------------------------------
# 3. CALCULS (DATA PROCESSING)
# ------------------------------------------------------------
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

def get_market_data(config):
    tickers = config['tickers']
    # Téléchargement unique pour la performance
    data = yf.download(tickers, period=config['period'], interval=config['interval'], group_by='ticker', progress=False)
    
    results = {}
    
    for ticker in tickers:
        try:
            # Gestion safe des données
            df = data[ticker].dropna()
            if len(df) < 20: continue
            
            close = df['Close']
            price_now = close.iloc[-1]
            price_past = close.shift(config['lookback_days']).iloc[-1]
            
            if pd.isna(price_now) or pd.isna(price_past) or price_past == 0: continue

            # Force Relative
            raw_move_pct = (price_now - price_past) / price_past
            atr = calculate_atr(df, config['atr_period']).iloc[-1]
            # Protection division par zéro ou ATR nul
            atr_pct = (atr / price_now) if price_now != 0 else 0.001
            strength = raw_move_pct / max(atr_pct, 0.0001)
            
            # Catégorisation
            if "=X" in ticker: cat = "FOREX"
            elif "=F" in ticker: cat = "COMMODITIES"
            elif "^" in ticker: cat = "INDICES"
            else: cat = "OTHER"
            
            # Nom propre
            display_name = ticker.replace('=X','').replace('=F','').replace('^','')
            mapping = {'DJI':'US30', 'GSPC':'SPX500', 'IXIC':'NAS100', 'FCHI':'CAC40', 'GDAXI':'DAX', 'GC':'GOLD', 'CL':'OIL', 'SI':'SILVER', 'HG':'COPPER'}
            display_name = mapping.get(display_name, display_name)

            results[ticker] = {
                'name': display_name,
                'raw_score': strength,
                'category': cat
            }
        except KeyError:
            continue

    if not results: return pd.DataFrame()

    df_res = pd.DataFrame.from_dict(results, orient='index')
    
    # Normalisation 0-10
    vals = df_res['raw_score'].values
    z = zscore(vals)
    z = np.clip(np.nan_to_num(z), -2.5, 2.5)
    df_res['score'] = 5 + (z / 5) * 10
    df_res['score'] = df_res['score'].clip(0, 10)
    
    return df_res.sort_values(by='score', ascending=False)

# ------------------------------------------------------------
# 4. RENDU HTML (FONCTIONS DE COULEUR)
# ------------------------------------------------------------
def get_color(score):
    # Palette Dégradé Rouge -> Gris -> Vert
    if score >= 8.5: return "#064e3b" # Vert très foncé (Strong Buy)
    if score >= 7.0: return "#166534" # Vert
    if score >= 6.0: return "#22c55e" # Vert clair
    if score >= 5.5: return "#4b5563" # Gris verdâtre
    
    if score <= 1.5: return "#7f1d1d" # Rouge très foncé (Strong Sell)
    if score <= 3.0: return "#991b1b" # Rouge
    if score <= 4.0: return "#ef4444" # Rouge clair
    if score <= 4.5: return "#4b5563" # Gris rougeâtre
    
    return "#374151" # Gris Neutre

def render_section(title, df_subset):
    """Génère le bloc HTML complet pour une section pour éviter les bugs d'affichage"""
    if df_subset.empty: return
    
    # 1. Titre
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    
    # 2. Construction du gros bloc HTML pour toutes les tuiles
    html_block = '<div class="heatmap-container">'
    
    for _, row in df_subset.iterrows():
        score = row['score']
        name = row['name']
        bg_color = get_color(score)
        
        # Le HTML de la tuile unique
        tile = f"""
        <div class="market-tile" style="background-color: {bg_color};">
            <div class="tile-symbol">{name}</div>
            <div class="tile-score">{score:.1f}</div>
        </div>
        """
        html_block += tile
        
    html_block += '</div>'
    
    # 3. Rendu unique pour éviter le texte brut
    st.markdown(html_block, unsafe_allow_html=True)

# ------------------------------------------------------------
# 5. APP PRINCIPALE
# ------------------------------------------------------------
st.title("🗺️ Market Heatmap Pro")

if st.button("🔄 SCANNER LE MARCHÉ", type="primary"):
    with st.spinner("Analyse de la force relative (Forex, Indices, Métaux)..."):
        df_final = get_market_data(CONFIG)
        
        if not df_final.empty:
            
            # Affichage par blocs
            fx = df_final[df_final['category'] == 'FOREX']
            indices = df_final[df_final['category'] == 'INDICES']
            commodities = df_final[df_final['category'] == 'COMMODITIES']
            
            render_section("💱 FOREX (Paires Majeures & Croisées)", fx)
            render_section("📊 INDICES MONDIAUX", indices)
            render_section("🪙 MATIÈRES PREMIÈRES", commodities)
            
        else:
            st.error("Erreur de connexion aux données. Réessayez.")
else:
    st.info("Cliquez sur le bouton pour générer la Heatmap.")
