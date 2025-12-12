import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore

# ------------------------------------------------------------
# 1. CONFIGURATION & STYLE (CSS MARKET MAP)
# ------------------------------------------------------------
st.set_page_config(page_title="Forex Heatmap Pro", layout="wide")

st.markdown("""
<style>
    /* Fond sombre */
    .stApp { background-color: #121212; }

    /* Conteneur Flex pour les tuiles (Alignement automatique) */
    .heatmap-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px; /* Espace entre les tuiles */
        justify-content: flex-start;
        padding: 10px 0;
    }

    /* La TUILE (Le rectangle coloré) */
    .market-tile {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        width: 130px;  /* Largeur fixe pour alignement propre */
        height: 70px;  /* Hauteur compacte */
        border-radius: 4px;
        color: white;
        font-family: 'Arial', sans-serif;
        box-shadow: 0 2px 4px rgba(0,0,0,0.4);
        transition: transform 0.2s;
        border: 1px solid rgba(255,255,255,0.1);
    }
    
    .market-tile:hover {
        transform: scale(1.05);
        z-index: 10;
        border-color: white;
        cursor: pointer;
    }

    /* Texte dans la tuile */
    .tile-symbol {
        font-weight: 800;
        font-size: 15px;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    
    .tile-score {
        font-size: 13px;
        font-weight: 400;
        opacity: 0.9;
    }
    
    /* Titres de section */
    .section-header {
        color: #8b949e;
        font-size: 16px;
        margin-top: 25px;
        margin-bottom: 10px;
        border-bottom: 1px solid #333;
        padding-bottom: 5px;
        font-family: sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# LISTE COMPLETE DES PAIRES (Cross inclus)
CONFIG = {
    'tickers': [
        # MAJEURS
        'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'AUDUSD=X', 'USDCAD=X', 'NZDUSD=X',
        # CROSS EUR
        'EURGBP=X', 'EURJPY=X', 'EURCHF=X', 'EURAUD=X', 'EURCAD=X', 'EURNZD=X',
        # CROSS GBP
        'GBPJPY=X', 'GBPCHF=X', 'GBPAUD=X', 'GBPCAD=X', 'GBPNZD=X',
        # CROSS AUD/NZD/CAD
        'AUDJPY=X', 'AUDCAD=X', 'AUDNZD=X', 'AUDCHF=X',
        'CADJPY=X', 'CADCHF=X', 'NZDJPY=X', 'NZDCHF=X', 'CHFJPY=X',
        # INDICES
        '^DJI', '^GSPC', '^IXIC', '^FCHI', '^GDAXI',
        # COMMODITIES
        'GC=F', 'CL=F'
    ],
    'period': '60d', 
    'interval': '1d', 
    'lookback_days': 3,
    'atr_period': 14
}

# ------------------------------------------------------------
# 2. MOTEUR DE CALCUL (Score 0-10)
# ------------------------------------------------------------
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

def get_market_data(config):
    tickers = config['tickers']
    # Téléchargement groupé pour la vitesse
    data = yf.download(tickers, period=config['period'], interval=config['interval'], group_by='ticker', progress=False)
    
    results = {}
    
    for ticker in tickers:
        try:
            df = data[ticker].dropna()
            if len(df) < 20: continue
            
            close = df['Close']
            price_now = close.iloc[-1]
            price_past = close.shift(config['lookback_days']).iloc[-1]
            
            if pd.isna(price_now) or pd.isna(price_past) or price_past == 0: continue

            # Mouvement brut %
            raw_move_pct = (price_now - price_past) / price_past
            
            # Ajustement Volatilité
            atr = calculate_atr(df, config['atr_period']).iloc[-1]
            atr_pct = (atr / price_now) if price_now != 0 else 0.001
            
            # Force normalisée
            strength = raw_move_pct / max(atr_pct, 0.0001)
            
            # Catégorisation simple
            if "=X" in ticker: cat = "FOREX"
            elif "=F" in ticker: cat = "COMMODITIES"
            elif "^" in ticker: cat = "INDICES"
            else: cat = "OTHER"
            
            # Nettoyage nom
            display_name = ticker.replace('=X','').replace('=F','').replace('^','')
            # Mapping noms connus
            name_map = {'DJI':'US30', 'GSPC':'SPX500', 'IXIC':'NAS100', 'FCHI':'CAC40', 'GDAXI':'DAX', 'GC':'GOLD', 'CL':'OIL'}
            display_name = name_map.get(display_name, display_name)

            results[ticker] = {
                'name': display_name,
                'raw_score': strength,
                'category': cat,
                'pct_change': raw_move_pct * 100
            }
        except KeyError:
            continue

    if not results: return pd.DataFrame()

    df_res = pd.DataFrame.from_dict(results, orient='index')
    
    # Z-Score -> Note de 0 à 10
    vals = df_res['raw_score'].values
    z = zscore(vals)
    z = np.clip(np.nan_to_num(z), -2.5, 2.5)
    df_res['score'] = 5 + (z / 5) * 10
    df_res['score'] = df_res['score'].clip(0, 10)
    
    return df_res.sort_values(by='score', ascending=False)

# ------------------------------------------------------------
# 3. GÉNÉRATEUR DE TUILES HTML
# ------------------------------------------------------------
def get_color_for_score(score):
    # Couleurs style "Finviz"
    # Vert Foncé -> Vert Clair -> Gris (Neutre) -> Rouge Clair -> Rouge Foncé
    if score >= 8.5: return "#006400" # Strongest Green
    if score >= 7.0: return "#228B22" # Green
    if score >= 6.0: return "#3CB371" # Medium Sea Green
    if score >= 5.5: return "#3d4d3d" # Slight Greenish Grey
    
    if score <= 1.5: return "#8B0000" # Strongest Red
    if score <= 3.0: return "#B22222" # Firebrick
    if score <= 4.0: return "#CD5C5C" # Indian Red
    if score <= 4.5: return "#4d3d3d" # Slight Reddish Grey
    
    return "#2c2c2c" # Neutral Grey

def render_heatmap(df_subset):
    html_block = '<div class="heatmap-container">'
    
    for _, row in df_subset.iterrows():
        score = row['score']
        name = row['name']
        
        bg_color = get_color_for_score(score)
        
        tile_html = f"""
        <div class="market-tile" style="background-color: {bg_color};">
            <div class="tile-symbol">{name}</div>
            <div class="tile-score">{score:.1f}</div>
        </div>
        """
        html_block += tile_html
        
    html_block += '</div>'
    st.markdown(html_block, unsafe_allow_html=True)

# ------------------------------------------------------------
# 4. INTERFACE
# ------------------------------------------------------------
st.title("🗺️ Forex Market Map")
st.write("Vue synthétique type 'Heatmap'. Vert = Hausse (Acheteur), Rouge = Baisse (Vendeur).")

if st.button("🔄 Scanner le Marché", type="primary"):
    with st.spinner("Analyse des flux..."):
        df = get_market_data(CONFIG)
        
        if not df.empty:
            
            # --- SECTION FOREX ---
            st.markdown('<div class="section-header">💱 FOREX (Majeurs & Cross)</div>', unsafe_allow_html=True)
            fx_data = df[df['category'] == 'FOREX']
            render_heatmap(fx_data)
            
            # --- SECTION INDICES ---
            st.markdown('<div class="section-header">📊 INDICES & ACTIONS</div>', unsafe_allow_html=True)
            ind_data = df[df['category'] == 'INDICES']
            render_heatmap(ind_data)
            
            # --- SECTION COMMODITIES ---
            st.markdown('<div class="section-header">🪙 MATIÈRES PREMIÈRES</div>', unsafe_allow_html=True)
            com_data = df[df['category'] == 'COMMODITIES']
            render_heatmap(com_data)
            
        else:
            st.error("Aucune donnée récupérée. Vérifiez votre connexion.")
