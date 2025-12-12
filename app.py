import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore

# ------------------------------------------------------------
# 1. CONFIGURATION VISUELLE (CSS FLUIDE)
# ------------------------------------------------------------
st.set_page_config(page_title="Market Heatmap", layout="wide")

st.markdown("""
<style>
    /* Fond sombre propre */
    .stApp { background-color: #0e1117; }

    /* Conteneur Grille (Flexbox) */
    .heatmap-container {
        display: flex;
        flex-wrap: wrap;       /* Passage à la ligne auto */
        gap: 8px;              /* Espace entre les tuiles */
        justify-content: flex-start;
        padding-bottom: 25px;
    }

    /* CARTE (Tuile) */
    .market-tile {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        width: 115px;          /* Largeur fixe */
        height: 65px;          /* Hauteur fixe */
        border-radius: 6px;
        color: white;
        box-shadow: 0 3px 6px rgba(0,0,0,0.3);
        border: 1px solid rgba(255,255,255,0.08);
        transition: transform 0.15s ease-in-out;
    }
    
    .market-tile:hover {
        transform: scale(1.08);
        border-color: rgba(255,255,255,0.6);
        z-index: 10;
        cursor: pointer;
    }

    /* Texte Symbole */
    .tile-symbol {
        font-family: 'Roboto', sans-serif;
        font-weight: 800;
        font-size: 14px;
        margin-bottom: 3px;
        text-shadow: 0 2px 2px rgba(0,0,0,0.6);
    }
    
    /* Texte Score */
    .tile-score {
        font-family: 'Courier New', monospace;
        font-weight: bold;
        font-size: 15px;
        background-color: rgba(0,0,0,0.25);
        padding: 1px 8px;
        border-radius: 4px;
    }

    /* Titres des sections */
    .section-header {
        font-size: 18px;
        font-weight: 600;
        color: #8b949e;
        margin-top: 10px;
        margin-bottom: 15px;
        border-bottom: 1px solid #30363d;
        padding-bottom: 5px;
        display: block;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 2. LISTE DES ACTIFS A SCANNER
# ------------------------------------------------------------
CONFIG = {
    'tickers': [
        # --- FOREX ---
        'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'AUDUSD=X', 'USDCAD=X', 'NZDUSD=X',
        'EURGBP=X', 'EURJPY=X', 'EURCHF=X', 'EURAUD=X', 'EURCAD=X', 'EURNZD=X',
        'GBPJPY=X', 'GBPCHF=X', 'GBPAUD=X', 'GBPCAD=X', 'GBPNZD=X',
        'AUDJPY=X', 'AUDCAD=X', 'AUDNZD=X', 'AUDCHF=X',
        'CADJPY=X', 'CADCHF=X', 'NZDJPY=X', 'NZDCHF=X', 'CHFJPY=X',
        
        # --- INDICES ---
        '^DJI', '^GSPC', '^IXIC', '^FCHI', '^GDAXI',
        
        # --- METAL / OIL ---
        'GC=F', 'CL=F', 'SI=F', 'HG=F'
    ],
    'period': '60d', 'interval': '1d', 'lookback_days': 3, 'atr_period': 14
}

# ------------------------------------------------------------
# 3. MOTEUR DE CALCUL
# ------------------------------------------------------------
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

def get_market_data(config):
    tickers = config['tickers']
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

            # Force Relative
            raw_move_pct = (price_now - price_past) / price_past
            atr = calculate_atr(df, config['atr_period']).iloc[-1]
            atr_pct = (atr / price_now) if price_now != 0 else 0.001
            strength = raw_move_pct / max(atr_pct, 0.0001)
            
            # Catégories
            if "=X" in ticker: cat = "FOREX"
            elif "=F" in ticker: cat = "COMMODITIES"
            elif "^" in ticker: cat = "INDICES"
            else: cat = "OTHER"
            
            # Noms propres
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
# 4. GÉNÉRATEUR HTML (SANS BUGS)
# ------------------------------------------------------------
def get_color(score):
    # Palette Finviz: Vert Foncé (Bull) -> Rouge Foncé (Bear)
    if score >= 8.5: return "#064e3b" # Strong Buy
    if score >= 7.0: return "#15803d" # Buy
    if score >= 6.0: return "#22c55e" # Weak Buy
    if score >= 5.5: return "#4b5563" # Neutral +
    
    if score <= 1.5: return "#7f1d1d" # Strong Sell
    if score <= 3.0: return "#b91c1c" # Sell
    if score <= 4.0: return "#ef4444" # Weak Sell
    if score <= 4.5: return "#4b5563" # Neutral -
    
    return "#374151" # Neutral Grey

def render_section_html(title, df_subset):
    if df_subset.empty: return ""
    
    # 1. Le Titre de la section
    html_output = f'<div class="section-header">{title}</div>'
    
    # 2. Ouverture du conteneur Flexbox
    html_output += '<div class="heatmap-container">'
    
    # 3. Boucle pour créer les tuiles
    for _, row in df_subset.iterrows():
        score = row['score']
        name = row['name']
        bg_color = get_color(score)
        
        # Le bloc HTML d'une seule tuile
        tile_html = f"""
        <div class="market-tile" style="background-color: {bg_color};">
            <div class="tile-symbol">{name}</div>
            <div class="tile-score">{score:.1f}</div>
        </div>
        """
        html_output += tile_html
        
    # 4. Fermeture du conteneur
    html_output += '</div>'
    
    return html_output

# ------------------------------------------------------------
# 5. APPLICATION STREAMLIT
# ------------------------------------------------------------
st.title("🗺️ Market Heatmap Pro")
st.write("Visualisation de force relative (Momentum vs Volatilité). Vert = Fort, Rouge = Faible.")

if st.button("🚀 ACTUALISER LE MARCHÉ", type="primary"):
    with st.spinner("Analyse en cours..."):
        df_final = get_market_data(CONFIG)
        
        if not df_final.empty:
            
            # --- Génération du HTML complet ---
            full_html = ""
            
            # Section Forex
            fx = df_final[df_final['category'] == 'FOREX']
            full_html += render_section_html("💱 FOREX (Paires)", fx)
            
            # Section Indices
            indices = df_final[df_final['category'] == 'INDICES']
            full_html += render_section_html("📊 INDICES MONDIAUX", indices)
            
            # Section Commodities
            commodities = df_final[df_final['category'] == 'COMMODITIES']
            full_html += render_section_html("🪙 MATIÈRES PREMIÈRES", commodities)
            
            # --- RENDU FINAL (Le point critique) ---
            # C'est cette ligne qui empêche le code de s'afficher en texte brut
            st.markdown(full_html, unsafe_allow_html=True)
            
        else:
            st.error("Aucune donnée disponible. Vérifiez votre connexion internet.")
else:
    st.info("Cliquez sur le bouton pour lancer le scan.")
