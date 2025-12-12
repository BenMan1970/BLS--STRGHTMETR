import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore

# ------------------------------------------------------------
# 1. CONFIGURATION & STYLES (COMPACT & GRID)
# ------------------------------------------------------------
st.set_page_config(page_title="Market Heatmap Pro", layout="wide")

st.markdown("""
<style>
    /* Fond global */
    .stApp { background-color: #0b0e11; }

    /* Style de la "Carte" pour chaque actif */
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: transform 0.2s;
    }
    .metric-card:hover {
        border-color: #58a6ff;
        transform: translateY(-2px);
    }

    /* En-tête de la carte (Symbole et Score) */
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .symbol-text {
        font-family: 'Roboto', sans-serif;
        font-weight: 700;
        font-size: 14px;
        color: #e6edf3;
    }
    .score-text {
        font-family: 'Courier New', monospace;
        font-weight: bold;
        font-size: 14px;
    }

    /* Conteneur de la jauge compacte */
    .gauge-container {
        display: flex;
        flex-direction: row;
        gap: 2px; /* Espace très fin */
        height: 8px; /* Hauteur réduite pour compacité */
        width: 100%;
        margin-top: 4px;
        position: relative;
    }

    .segment {
        flex: 1;
        height: 100%;
        border-radius: 2px;
    }

    /* Le curseur triangle (adapté à la petite taille) */
    .cursor-marker {
        position: absolute;
        top: 10px; /* Juste sous la barre */
        width: 0; 
        height: 0; 
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-bottom: 5px solid #fff;
        transform: translateX(-50%);
        transition: left 0.4s ease-out;
    }
    
    /* Sections */
    .section-title {
        color: #8b949e;
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin: 20px 0 10px 0;
        border-bottom: 1px solid #30363d;
        padding-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Liste complète (Forex Majeurs + Cross + Indices + Métaux)
CONFIG = {
    'tickers': {
        # --- MAJEURS & MINEURS (FOREX) ---
        'EURUSD=X': 'FX', 'GBPUSD=X': 'FX', 'USDJPY=X': 'FX', 'USDCHF=X': 'FX',
        'AUDUSD=X': 'FX', 'USDCAD=X': 'FX', 'NZDUSD=X': 'FX',
        'EURGBP=X': 'FX', 'EURJPY=X': 'FX', 'EURCHF=X': 'FX', 'EURAUD=X': 'FX',
        'GBPJPY=X': 'FX', 'GBPCHF=X': 'FX', 'AUDJPY=X': 'FX', 'CADJPY=X': 'FX',
        'CHFJPY=X': 'FX', 'AUDCAD=X': 'FX', 'AUDNZD=X': 'FX', 'NZDJPY=X': 'FX',
        
        # --- INDICES ---
        '^DJI': 'INDICES',      # Dow Jones
        '^GSPC': 'INDICES',     # S&P 500
        '^IXIC': 'INDICES',     # Nasdaq
        '^FCHI': 'INDICES',     # CAC 40
        '^GDAXI': 'INDICES',    # DAX
        
        # --- MATIERES PREMIERES ---
        'GC=F': 'COMMODITIES',  # Gold
        'SI=F': 'COMMODITIES',  # Silver
        'CL=F': 'COMMODITIES',  # Crude Oil
        'HG=F': 'COMMODITIES'   # Copper
    },
    'period': '60d', 'interval': '1d', 
    'lookback_days': 3,  # Momentum sur 3 jours
    'atr_period': 14
}

# ------------------------------------------------------------
# 2. CALCULS (Score par PAIRE)
# ------------------------------------------------------------
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

def compute_pair_strength(config=CONFIG):
    tickers_map = config['tickers']
    tickers_list = list(tickers_map.keys())
    
    # Téléchargement groupé
    data = yf.download(tickers_list, period=config['period'], interval=config['interval'], group_by='ticker', progress=False)
    
    results = {}
    
    for ticker in tickers_list:
        try:
            # Gestion des colonnes MultiIndex
            df = data[ticker].dropna()
            if len(df) < 20: continue
            
            close = df['Close']
            price_now = close.iloc[-1]
            price_past = close.shift(config['lookback_days']).iloc[-1]
            
            if pd.isna(price_now) or pd.isna(price_past) or price_past == 0: continue

            # 1. Calcul du mouvement brut (%)
            raw_move_pct = (price_now - price_past) / price_past
            
            # 2. Normalisation par la volatilité (ATR)
            # Pour comparer le mouvement de l'Or vs l'EURUSD équitablement
            atr = calculate_atr(df, config['atr_period']).iloc[-1]
            atr_pct = (atr / price_now) if price_now != 0 else 0.001
            atr_pct = max(atr_pct, 0.0001) # Sécurité division par zéro
            
            normalized_strength = raw_move_pct / atr_pct
            
            results[ticker] = {
                'raw_score': normalized_strength,
                'category': tickers_map[ticker]
            }
        except KeyError:
            continue

    if not results:
        return pd.DataFrame()

    df_res = pd.DataFrame.from_dict(results, orient='index')
    
    # 3. Z-Score global pour obtenir une note de 0 à 10
    # 0 = Très Vendeur, 5 = Neutre, 10 = Très Acheteur
    vals = df_res['raw_score'].values
    z = zscore(vals)
    z = np.clip(np.nan_to_num(z), -2.5, 2.5) # On clip à 2.5 écarts types
    
    # Transformation Z (-2.5 à 2.5) vers (0 à 10)
    df_res['score'] = 5 + (z / 5) * 10 
    df_res['score'] = df_res['score'].clip(0, 10)
    
    # Nettoyage du nom du ticker pour l'affichage (retirer =X, =F...)
    df_res['display_name'] = df_res.index.str.replace('=X','').str.replace('=F','').str.replace('^','')
    
    # Remplacer les noms cryptiques par des noms communs
    names_map = {'DJI':'US30', 'GSPC':'SPX500', 'IXIC':'NAS100', 'FCHI':'CAC40', 'GDAXI':'DAX40', 'GC':'GOLD', 'SI':'SILVER', 'CL':'OIL', 'HG':'COPPER'}
    df_res['display_name'] = df_res['display_name'].replace(names_map)
    
    return df_res.sort_values(by='score', ascending=False)

# ------------------------------------------------------------
# 3. VISUEL HTML (Version "Micro")
# ------------------------------------------------------------
def get_mini_gauge(score):
    # Palette Dégradé: Rouge (0) -> Gris (5) -> Vert (10)
    # Pour le trading de paires : Rouge = Baisse, Vert = Hausse
    colors = [
        "#ff2b2b", "#ff5252", "#ff7b7b", "#ffa3a3", # Bearish (Red)
        "#4a4f55", "#4a4f55",                       # Neutral (Grey)
        "#85e085", "#5cd65c", "#33cc33", "#00b300"  # Bullish (Green)
    ]
    
    score_int = int(round(score))
    score_int = max(0, min(9, score_int)) # Index 0-9
    
    segments = ""
    for i in range(10):
        # Couleur dynamique selon la position dans l'échelle
        base_color = colors[i]
        
        # Logique d'allumage : On allume tout ce qui est "avant" le score pour faire une barre de progression ?
        # NON, pour un indicateur type RSI/Force, on veut souvent voir l'intensité.
        # Approche "Equalizer" :
        
        # Opacité : Allumé si i <= score (Barre pleine)
        opacity = "1.0" if i <= score else "0.15"
        
        # Si c'est neutre (milieu), on garde gris foncé
        bg = base_color
        
        # Effet Néon seulement sur les segments allumés actifs
        shadow = f"0 0 5px {bg}" if opacity == "1.0" else "none"
        
        segments += f'<div class="segment" style="background:{bg}; opacity:{opacity}; box-shadow:{shadow};"></div>'
    
    cursor_pos = (score / 10) * 100
    
    return f"""
    <div style="position:relative;">
        <div class="gauge-container">{segments}</div>
        <div class="cursor-marker" style="left:{cursor_pos}%;"></div>
    </div>
    """

# ------------------------------------------------------------
# 4. RENDU STREAMLIT (GRID)
# ------------------------------------------------------------

st.title("🌐 Global Market Pulse")
st.write("Analyse de momentum cross-assets (Paires, Indices, Métaux).")

if st.button("Actualiser les données", type="primary"):
    with st.spinner("Analyse du marché..."):
        df = compute_pair_strength()
        
        if not df.empty:
            
            # Fonction pour afficher une grille d'une catégorie donnée
            def display_category(category_name, filter_key):
                subset = df[df['category'] == filter_key]
                if subset.empty: return
                
                st.markdown(f"<div class='section-title'>{category_name}</div>", unsafe_allow_html=True)
                
                # Création de 4 colonnes
                cols = st.columns(4)
                
                for idx, (ticker, row) in enumerate(subset.iterrows()):
                    score = row['score']
                    name = row['display_name']
                    
                    # Couleur du texte du score
                    if score >= 7: score_color = "#00e676" # Vert vif
                    elif score <= 3: score_color = "#ff5252" # Rouge vif
                    else: score_color = "#b0b0b0" # Gris
                    
                    # Choix de la colonne (0, 1, 2, 3)
                    col_idx = idx % 4
                    
                    with cols[col_idx]:
                        gauge_html = get_mini_gauge(score)
                        
                        # Carte HTML complète
                        card_html = f"""
                        <div class="metric-card">
                            <div class="card-header">
                                <span class="symbol-text">{name}</span>
                                <span class="score-text" style="color:{score_color}">{score:.1f}</span>
                            </div>
                            {gauge_html}
                        </div>
                        """
                        st.markdown(card_html, unsafe_allow_html=True)

            # Affichage par catégories
            display_category("📊 Indices & Actions", "INDICES")
            display_category("🪙 Matières Premières", "COMMODITIES")
            display_category("💱 Forex (Majeurs & Cross)", "FX")

else:
    st.info("Cliquez sur le bouton pour scanner les marchés.")
