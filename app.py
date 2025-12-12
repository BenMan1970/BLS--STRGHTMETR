import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

# ------------------------------------------------------------
# 1. STYLE CSS (AJOUT DU STYLE "MATRIX" COLONNES)
# ------------------------------------------------------------
st.set_page_config(page_title="Market Heatmap Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }

    /* CONTENEUR GLOBAL FLEX */
    .heatmap-wrap {
        display: flex;
        flex-direction: column;
        gap: 20px;
        width: 100%;
        overflow-x: auto;
    }

    /* MATRICE FOREX (Le style Barchart) */
    .forex-matrix {
        display: flex;
        flex-direction: row;
        gap: 10px;
        justify-content: flex-start; /* Aligné à gauche */
        padding-bottom: 20px;
    }

    /* UNE COLONNE DE DEVISE */
    .currency-col {
        display: flex;
        flex-direction: column;
        gap: 4px;
        min-width: 130px;
    }

    /* EN-TÊTE DE COLONNE (ex: EUR) */
    .col-header {
        font-family: 'Arial', sans-serif;
        font-weight: 900;
        font-size: 18px;
        color: #e6edf3;
        text-align: center;
        padding: 5px 0;
        border-bottom: 2px solid #30363d;
        margin-bottom: 5px;
        background-color: #161b22;
        border-radius: 4px;
    }

    /* TUILE STANDARD (Pour Indices/Commo) */
    .heatmap-container-standard {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: flex-start;
    }

    /* LA TUILE (Design conservé mais taille ajustée pour la matrice) */
    .market-tile {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0 10px;
        width: 100%; /* Prend la largeur de la colonne */
        height: 45px; /* Plus compact comme Barchart */
        border-radius: 4px;
        color: white;
        font-size: 13px;
        font-weight: bold;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        border: 1px solid rgba(255,255,255,0.05);
        transition: transform 0.1s;
    }
    
    .market-tile:hover {
        transform: scale(1.02);
        border-color: rgba(255,255,255,0.4);
        z-index: 10;
    }

    /* TEXTE DANS LA TUILE */
    .tile-pair { font-family: sans-serif; }
    .tile-val { font-family: 'Courier New', monospace; }

    .section-header {
        font-family: 'Helvetica', sans-serif;
        font-size: 18px;
        font-weight: 600;
        color: #8b949e;
        margin-top: 25px;
        margin-bottom: 15px;
        border-bottom: 1px solid #30363d;
        padding-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 2. CONFIGURATION & DONNÉES
# ------------------------------------------------------------
CONFIG = {
    'instruments': {
        'FOREX': [
            'EUR_USD', 'GBP_USD', 'USD_JPY', 'USD_CHF', 'AUD_USD', 'USD_CAD', 'NZD_USD',
            'EUR_GBP', 'EUR_JPY', 'EUR_CHF', 'EUR_AUD', 'EUR_CAD', 'EUR_NZD',
            'GBP_JPY', 'GBP_CHF', 'GBP_AUD', 'GBP_CAD', 'GBP_NZD',
            'AUD_JPY', 'AUD_CAD', 'AUD_NZD', 'AUD_CHF',
            'CAD_JPY', 'CAD_CHF', 'NZD_JPY', 'NZD_CHF', 'CHF_JPY'
        ],
        'INDICES': [
            'SPX500_USD', 'NAS100_USD', 'US30_USD', 'DE30_EUR', 'FR40_EUR', 
            'UK100_GBP', 'JP225_USD', 'AUS200_AUD', 'HK33_HKD'
        ],
        'COMMODITIES': [
            'XAU_USD', 'XAG_USD', 'BCO_USD', 'WTICO_USD', 'NATGAS_USD', 'XCU_USD'
        ]
    },
    'lookback_days': 1
}

DISPLAY_NAMES = {
    'SPX500_USD': 'SPX500', 'NAS100_USD': 'NAS100', 'US30_USD': 'US30',
    'DE30_EUR': 'DAX', 'FR40_EUR': 'CAC40', 'UK100_GBP': 'FTSE100',
    'JP225_USD': 'NIKKEI', 'AUS200_AUD': 'ASX200', 'HK33_HKD': 'HANGSENG',
    'XAU_USD': 'GOLD', 'XAG_USD': 'SILVER', 'BCO_USD': 'BRENT', 
    'WTICO_USD': 'WTI', 'NATGAS_USD': 'GAS', 'XCU_USD': 'COPPER'
}

def get_oanda_credentials():
    try:
        return st.secrets["OANDA_ACCOUNT_ID"], st.secrets["OANDA_ACCESS_TOKEN"]
    except:
        return None, None

def fetch_oanda_candles(instrument, count=10):
    account_id, access_token = get_oanda_credentials()
    if not account_id: return None
    
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"count": count, "granularity": "D"}
    try:
        url = f"https://api-fxpractice.oanda.com/v3/instruments/{instrument}/candles"
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            candles = response.json().get('candles', [])
            if not candles: return None
            df = pd.DataFrame([{'close': float(c['mid']['c'])} for c in candles])
            return df
    except:
        return None
    return None

def get_market_data(config):
    results = {}
    if not get_oanda_credentials()[0]:
        st.error("❌ Credentials manquants")
        return pd.DataFrame()
    
    total = sum(len(v) for v in config['instruments'].values())
    prog = st.progress(0)
    curr = 0
    
    for category, instruments in config['instruments'].items():
        for instrument in instruments:
            try:
                df = fetch_oanda_candles(instrument, count=config['lookback_days'] + 5)
                if df is not None and len(df) > config['lookback_days']:
                    now = df['close'].iloc[-1]
                    past = df['close'].shift(config['lookback_days']).iloc[-1]
                    pct = (now - past) / past * 100
                    
                    name = DISPLAY_NAMES.get(instrument, instrument.replace('_', '/'))
                    results[instrument] = {'name': name, 'pct': pct, 'cat': category}
            except: pass
            curr += 1
            prog.progress(curr/total)
            
    prog.empty()
    return pd.DataFrame.from_dict(results, orient='index')

# ------------------------------------------------------------
# 3. LOGIQUE DE COULEUR BARCHART
# ------------------------------------------------------------
def get_color(pct):
    if pct >= 0.50: return "#064e3b" # Vert Foncé
    if pct >= 0.25: return "#15803d"
    if pct >= 0.10: return "#16a34a"
    if pct >= 0.01: return "#4ade80" # Vert Clair
    
    if pct <= -0.50: return "#7f1d1d" # Rouge Foncé
    if pct <= -0.25: return "#b91c1c"
    if pct <= -0.10: return "#dc2626"
    if pct <= -0.01: return "#f87171" # Rouge Clair
    
    return "#374151" # Gris (Neutre)

# ------------------------------------------------------------
# 4. GÉNÉRATEUR MATRICE FOREX (L'ALGORITHME INTELLIGENT)
# ------------------------------------------------------------
def generate_forex_matrix_html(df):
    """
    Transforme les données linéaires en une Matrice structurée par devise.
    Crée les paires inverses (ex: EURUSD -> USDEUR) pour remplir la grille.
    """
    forex_df = df[df['cat'] == 'FOREX']
    if forex_df.empty: return ""
    
    # 1. Expansion des données (Créer les inverses)
    matrix_data = []
    
    for symbol, row in forex_df.iterrows():
        # symbol est format OANDA: "EUR_USD"
        parts = symbol.split('_')
        if len(parts) != 2: continue
        
        base, quote = parts[0], parts[1]
        pct = row['pct']
        
        # Ajouter la paire originale (Base = EUR)
        matrix_data.append({
            'base': base, 
            'pair_display': f"{base}/{quote}", 
            'pct': pct
        })
        
        # Ajouter la paire inverse (Base = USD)
        # L'inverse mathématique approximatif du % est juste le signe opposé pour les petits %
        matrix_data.append({
            'base': quote, 
            'pair_display': f"{quote}/{base}", 
            'pct': -pct 
        })
        
    df_matrix = pd.DataFrame(matrix_data)
    
    # 2. Calculer le score de chaque devise (Moyenne des variations)
    # Plus le score est haut, plus la devise est "Forte" aujourd'hui -> À gauche
    currency_strength = df_matrix.groupby('base')['pct'].mean().sort_values(ascending=False)
    sorted_currencies = currency_strength.index.tolist()
    
    # 3. Construire le HTML
    html = '<div class="forex-matrix">'
    
    for currency in sorted_currencies:
        # Obtenir toutes les paires pour cette devise, triées par performance
        pairs_for_currency = df_matrix[df_matrix['base'] == currency].sort_values(by='pct', ascending=False)
        
        if pairs_for_currency.empty: continue
        
        html += f'<div class="currency-col">'
        html += f'<div class="col-header">{currency}</div>'
        
        for _, row in pairs_for_currency.iterrows():
            pct = row['pct']
            bg = get_color(pct)
            symbol = row['pair_display']
            
            html += f'''
            <div class="market-tile" style="background-color: {bg};">
                <span class="tile-pair">{symbol}</span>
                <span class="tile-val">{pct:+.2f}%</span>
            </div>
            '''
        
        html += '</div>' # Fin colonne
        
    html += '</div>'
    return html

def generate_standard_grid_html(df, category):
    subset = df[df['cat'] == category].sort_values(by='pct', ascending=False)
    if subset.empty: return ""
    
    html = '<div class="heatmap-container-standard">'
    for _, row in subset.iterrows():
        pct = row['pct']
        bg = get_color(pct)
        # Pour les indices/commo, on garde le format "Tuile Carrée" un peu plus large
        html += f'''
        <div class="market-tile" style="width: 120px; height: 70px; flex-direction: column; justify-content: center; background-color: {bg};">
            <div style="margin-bottom:4px;">{row['name']}</div>
            <div class="tile-val">{pct:+.2f}%</div>
        </div>
        '''
    html += '</div>'
    return html

# ------------------------------------------------------------
# 5. APP PRINCIPALE
# ------------------------------------------------------------
st.title("🗺️ Market Map Pro (Matrix Edition)")

with st.sidebar:
    st.header("Paramètres")
    CONFIG['lookback_days'] = st.slider("Horizon (Jours)", 1, 30, 1)
    
    creds = get_oanda_credentials()
    if creds[0]: st.success("OANDA Connecté")
    else: st.error("OANDA Déconnecté")
    
    st.info("Le mode Matrix trie les devises de la plus forte (Gauche) à la plus faible (Droite).")

if st.button("🔄 ACTUALISER LA CARTE", type="primary"):
    with st.spinner("Analyse du marché en cours..."):
        df_res = get_market_data(CONFIG)
        
        if not df_res.empty:
            # 1. Générer le HTML FOREX (Matrix)
            html_forex = generate_forex_matrix_html(df_res)
            
            # 2. Générer le HTML Indices/Commo (Standard)
            html_indices = generate_standard_grid_html(df_res, 'INDICES')
            html_commo = generate_standard_grid_html(df_res, 'COMMODITIES')
            
            # 3. Assemblage Final
            full_html = f"""
            <div class="section-header">💱 FOREX STRENGTH MATRIX (De Fort à Faible)</div>
            <div class="heatmap-wrap">
                {html_forex}
            </div>
            
            <div class="section-header">📊 INDICES MONDIAUX</div>
            {html_indices}
            
            <div class="section-header">🪙 MATIÈRES PREMIÈRES</div>
            {html_commo}
            """
            
            st.components.v1.html(
                f"""
                <!DOCTYPE html>
                <html><head><style>
                    body {{ margin: 0; background: transparent; color: white; font-family: sans-serif; }}
                    /* Inclusion du CSS défini plus haut */
                    {st.markdown} 
                    /* Hack pour injecter le style dans l'iframe */
                    .forex-matrix {{ display: flex; gap: 8px; }}
                    .currency-col {{ display: flex; flex-direction: column; gap: 4px; min-width: 110px; }}
                    .col-header {{ text-align: center; font-weight: bold; padding: 5px; background: #21262d; color: #8b949e; margin-bottom: 5px; border-radius: 4px;}}
                    .market-tile {{ display: flex; justify-content: space-between; align-items: center; padding: 8px; border-radius: 4px; font-size: 12px; font-weight: bold; color: white; margin-bottom: 2px; }}
                    .section-header {{ font-size: 16px; color: #8b949e; border-bottom: 1px solid #30363d; padding: 10px 0; margin-bottom: 10px; font-weight: bold; font-family: Helvetica; }}
                    .heatmap-container-standard {{ display: flex; flex-wrap: wrap; gap: 8px; }}
                </style></head><body>{full_html}</body></html>
                """,
                height=1200,
                scrolling=True
            )
        else:
            st.error("Pas de données.")
