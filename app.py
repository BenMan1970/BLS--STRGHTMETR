import streamlit as st
import pandas as pd
import requests

# ------------------------------------------------------------
# 1. STYLE CSS (Mise à jour pour le style "Totem / Empilé")
# ------------------------------------------------------------
st.set_page_config(page_title="Market Heatmap Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }

    /* CONTENEUR GLOBAL HORIZONTAL */
    .heatmap-wrap {
        display: flex;
        flex-direction: row;
        gap: 12px; /* Espace entre les colonnes */
        width: 100%;
        overflow-x: auto;
        padding-bottom: 20px;
        align-items: flex-start; /* Aligner les colonnes en haut */
    }

    /* UNE COLONNE DE DEVISE (Le Totem) */
    .currency-col {
        display: flex;
        flex-direction: column;
        gap: 2px; /* Petit espace entre les tuiles empilées */
        min-width: 130px;
    }

    /* LE SÉPARATEUR CENTRAL (ex: EUR, USD...) */
    .currency-separator {
        font-family: 'Arial', sans-serif;
        font-weight: 900;
        font-size: 15px;
        color: #333;
        background-color: #e6edf3; /* Gris clair / Blanc comme Barchart */
        text-align: left;
        padding: 4px 8px;
        margin: 4px 0;
        border-radius: 2px;
        text-transform: uppercase;
        box-shadow: 0 1px 3px rgba(0,0,0,0.5);
    }

    /* LA TUILE FOREX (Fine et rectangulaire) */
    .forex-tile {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0 8px;
        width: 100%;
        height: 28px; /* Hauteur compacte */
        color: white;
        font-size: 12px;
        font-weight: bold;
        border-radius: 2px;
        transition: filter 0.2s;
    }
    
    .forex-tile:hover {
        filter: brightness(1.2);
        cursor: pointer;
    }

    /* POLICE SPÉCIFIQUE */
    .tile-pair { font-family: sans-serif; opacity: 0.9; }
    .tile-val { font-family: 'Courier New', monospace; }

    /* TITRES */
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
# 2. CONFIGURATION & DATAS (INCHANGÉ)
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
        'INDICES': ['SPX500_USD', 'NAS100_USD', 'US30_USD', 'DE30_EUR', 'FR40_EUR', 'UK100_GBP', 'JP225_USD', 'AUS200_AUD', 'HK33_HKD'],
        'COMMODITIES': ['XAU_USD', 'XAG_USD', 'BCO_USD', 'WTICO_USD', 'NATGAS_USD', 'XCU_USD']
    },
    'lookback_days': 1
}

DISPLAY_NAMES = {
    'SPX500_USD': 'SPX500', 'NAS100_USD': 'NAS100', 'DE30_EUR': 'DAX', 'XAU_USD': 'GOLD', 'XAG_USD': 'SILVER', 'BCO_USD': 'BRENT'
}

def get_oanda_credentials():
    try: return st.secrets["OANDA_ACCOUNT_ID"], st.secrets["OANDA_ACCESS_TOKEN"]
    except: return None, None

def fetch_oanda_candles(instrument, count=10):
    acct, token = get_oanda_credentials()
    if not acct: return None
    try:
        url = f"https://api-fxpractice.oanda.com/v3/instruments/{instrument}/candles?count={count}&granularity=D"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            candles = resp.json().get('candles', [])
            if candles: return pd.DataFrame([{'close': float(c['mid']['c'])} for c in candles])
    except: pass
    return None

def get_market_data(config):
    results = {}
    if not get_oanda_credentials()[0]: return pd.DataFrame()
    
    total = sum(len(v) for v in config['instruments'].values())
    prog = st.progress(0); curr = 0
    
    for category, instruments in config['instruments'].items():
        for instrument in instruments:
            try:
                df = fetch_oanda_candles(instrument, count=config['lookback_days']+5)
                if df is not None and len(df) > config['lookback_days']:
                    now = df['close'].iloc[-1]
                    past = df['close'].shift(config['lookback_days']).iloc[-1]
                    pct = (now - past) / past * 100
                    name = DISPLAY_NAMES.get(instrument, instrument.replace('_', '/'))
                    results[instrument] = {'name': name, 'pct': pct, 'cat': category}
            except: pass
            curr += 1; prog.progress(curr/total)
    prog.empty()
    return pd.DataFrame.from_dict(results, orient='index')

# ------------------------------------------------------------
# 3. LOGIQUE COULEUR & MATRIX (LE COEUR DU DESIGN)
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
    
    return "#4b5563" # Gris si 0.00%

def generate_forex_matrix_html(df):
    forex_df = df[df['cat'] == 'FOREX']
    if forex_df.empty: return ""
    
    # 1. Structuration des données (Création des inverses)
    # On crée un dictionnaire : data[DEVISE]['items'] = liste de paires
    data = {}
    
    for symbol, row in forex_df.iterrows():
        parts = symbol.split('_') # ex: EUR_USD
        if len(parts) != 2: continue
        base, quote = parts[0], parts[1]
        pct = row['pct']
        
        # Initialisation si n'existe pas
        if base not in data: data[base] = []
        if quote not in data: data[quote] = []
        
        # Ajout direct (ex: EUR dans colonne EUR)
        data[base].append({'pair': f"{base}/{quote}", 'pct': pct, 'other': quote})
        
        # Ajout inverse (ex: USD dans colonne USD, valeur inversée)
        data[quote].append({'pair': f"{quote}/{base}", 'pct': -pct, 'other': base})
    
    # 2. Trier les colonnes (Les Devises) par force globale
    # On calcule la moyenne des % de chaque devise pour savoir qui est à gauche (Fort) ou à droite (Faible)
    currency_scores = {curr: sum(d['pct'] for d in items)/len(items) for curr, items in data.items()}
    sorted_currencies = sorted(currency_scores, key=currency_scores.get, reverse=True)
    
    # 3. Génération du HTML
    html = '<div class="heatmap-wrap">'
    
    for curr in sorted_currencies:
        items = data[curr]
        
        # Séparer Gagnants (Verts) et Perdants (Rouges)
        winners = [x for x in items if x['pct'] >= 0.005] # Seuil léger pour le 0
        losers = [x for x in items if x['pct'] < -0.005]
        unchanged = [x for x in items if -0.005 <= x['pct'] < 0.005]
        
        # TRI IMPORTANT POUR LE LOOK "EMPILÉ" :
        # - Les verts : du plus fort (haut) au moins fort (bas) -> Descending
        # - Les rouges : du moins faible (haut) au plus faible (bas) -> Descending aussi (-0.01 est > -0.50)
        #   Mathématiquement -0.1 est plus grand que -0.5, donc un tri Descending met -0.1 en haut et -0.5 en bas.
        #   C'est exactement ce qu'on veut : les petites variations près du centre, les grosses aux extrémités.
        
        winners.sort(key=lambda x: x['pct'], reverse=True)
        losers.sort(key=lambda x: x['pct'], reverse=True) 
        
        # Tout mettre dans la liste losers pour l'affichage 'unchanged' si on veut, ou les traiter à part.
        # Ici on ajoute les 'unchanged' aux winners ou losers selon le signe, ou on les affiche en gris.
        # Pour simplifier comme Barchart :
        
        html += '<div class="currency-col">'
        
        # --- PILE VERTE (HAUT) ---
        for item in winners:
            bg = get_color(item['pct'])
            html += f'''
            <div class="forex-tile" style="background-color: {bg};">
                <span class="tile-pair">{item['other']}</span>
                <span class="tile-val">+{item['pct']:.2f}%</span>
            </div>
            '''
            
        # --- SÉPARATEUR CENTRAL (NOM DE LA DEVISE) ---
        html += f'<div class="currency-separator">{curr}</div>'
        
        # --- PILE GRISE (NEUTRE) ---
        for item in unchanged:
             html += f'''
            <div class="forex-tile" style="background-color: #4b5563;">
                <span class="tile-pair">{item['other']}</span>
                <span class="tile-val">unch</span>
            </div>
            '''

        # --- PILE ROUGE (BAS) ---
        for item in losers:
            bg = get_color(item['pct'])
            html += f'''
            <div class="forex-tile" style="background-color: {bg};">
                <span class="tile-pair">{item['other']}</span>
                <span class="tile-val">{item['pct']:.2f}%</span>
            </div>
            '''
            
        html += '</div>' # Fin colonne
        
    html += '</div>'
    return html

def generate_standard_grid(df, cat):
    subset = df[df['cat'] == cat].sort_values(by='pct', ascending=False)
    if subset.empty: return ""
    html = '<div style="display:flex; flex-wrap:wrap; gap:8px;">'
    for _, row in subset.iterrows():
        bg = get_color(row['pct'])
        html += f'''
        <div style="background:{bg}; width:110px; height:60px; display:flex; flex-direction:column; justify-content:center; align-items:center; border-radius:4px; color:white; font-weight:bold; box-shadow:0 2px 4px rgba(0,0,0,0.3);">
            <div style="font-size:12px; margin-bottom:4px;">{row['name']}</div>
            <div style="font-family:monospace; font-size:14px;">{row['pct']:+.2f}%</div>
        </div>'''
    html += '</div>'
    return html

# ------------------------------------------------------------
# 4. RENDU STREAMLIT
# ------------------------------------------------------------
st.title("🗺️ Market Map Pro (Barchart Style)")

with st.sidebar:
    st.header("Réglages")
    CONFIG['lookback_days'] = st.slider("Jours", 1, 30, 1)
    if st.secrets.get("OANDA_ACCOUNT_ID"): st.success("Connecté à OANDA")

if st.button("🚀 ACTUALISER", type="primary"):
    df_res = get_market_data(CONFIG)
    
    if not df_res.empty:
        html_forex = generate_forex_matrix_html(df_res)
        html_indices = generate_standard_grid(df_res, 'INDICES')
        html_commo = generate_standard_grid(df_res, 'COMMODITIES')
        
        st.components.v1.html(
            f"""
            <!DOCTYPE html>
            <html><head><style>
                body {{ margin: 0; background: transparent; font-family: sans-serif; }}
                {st.markdown}
                /* Recopie des styles pour l'iframe (nécessaire dans Streamlit components) */
                .heatmap-wrap {{ display: flex; gap: 10px; align-items: flex-start; padding-bottom: 20px; }}
                .currency-col {{ display: flex; flex-direction: column; gap: 2px; min-width: 120px; }}
                .currency-separator {{ background: #e6edf3; color: #111; font-weight: 900; padding: 5px 10px; border-radius: 2px; text-align: left; font-size: 14px; margin: 4px 0; }}
                .forex-tile {{ display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; color: white; font-size: 12px; font-weight: bold; border-radius: 2px; margin-bottom: 1px; min-height: 24px; }}
                .tile-val {{ font-family: monospace; }}
                .section-header {{ color: #8b949e; font-size: 18px; font-weight: bold; margin: 20px 0 10px 0; border-bottom: 1px solid #333; }}
            </style></head><body>
                <div class="section-header">💱 FOREX MAP</div>
                {html_forex}
                
                <div class="section-header">📊 INDICES</div>
                {html_indices}
                
                <div class="section-header">🪙 MATIÈRES PREMIÈRES</div>
                {html_commo}
            </body></html>
            """,
            height=900, scrolling=True
        )
