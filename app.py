import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Market Heatmap Pro", layout="wide")

# ------------------------------------------------------------
# 1. CONFIGURATION & DONNÉES
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
    'SPX500_USD': 'SPX500', 'NAS100_USD': 'NAS100', 'DE30_EUR': 'DAX', 
    'XAU_USD': 'GOLD', 'XAG_USD': 'SILVER', 'BCO_USD': 'BRENT'
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
# 2. GÉNÉRATION HTML/CSS (INTEGRÉ POUR L'IFRAME)
# ------------------------------------------------------------
def get_color(pct):
    if pct >= 0.50: return "#004d00" # Vert très foncé
    if pct >= 0.25: return "#006400"
    if pct >= 0.10: return "#008000"
    if pct >= 0.01: return "#00a000" # Vert Barchart
    
    if pct <= -0.50: return "#8b0000" # Rouge très foncé
    if pct <= -0.25: return "#a00000"
    if pct <= -0.10: return "#b00000"
    if pct <= -0.01: return "#cc0000" # Rouge Barchart
    
    return "#555" # Gris neutre

def generate_report(df):
    forex_df = df[df['cat'] == 'FOREX']
    
    # --- LOGIQUE DE TRI (MATRIX) ---
    data = {}
    if not forex_df.empty:
        for symbol, row in forex_df.iterrows():
            parts = symbol.split('_')
            if len(parts) != 2: continue
            base, quote = parts[0], parts[1]
            pct = row['pct']
            
            if base not in data: data[base] = []
            if quote not in data: data[quote] = []
            
            data[base].append({'pair': f"{base}/{quote}", 'pct': pct, 'other': quote})
            data[quote].append({'pair': f"{quote}/{base}", 'pct': -pct, 'other': base})
    
    # Tri des devises par force globale (Moyenne des variations)
    currency_scores = {curr: sum(d['pct'] for d in items)/len(items) for curr, items in data.items()}
    sorted_currencies = sorted(currency_scores, key=currency_scores.get, reverse=True)

    # --- CONSTRUCTION DU HTML ---
    html_forex = '<div class="matrix-container">'
    
    for curr in sorted_currencies:
        items = data[curr]
        
        # Séparation
        winners = [x for x in items if x['pct'] >= 0.005]
        losers = [x for x in items if x['pct'] < -0.005]
        unchanged = [x for x in items if -0.005 <= x['pct'] < 0.005]
        
        # Tri visuel (Le plus fort en haut, le plus faible en bas)
        winners.sort(key=lambda x: x['pct'], reverse=True) 
        losers.sort(key=lambda x: x['pct'], reverse=True) # -0.01 en haut, -0.50 en bas
        
        html_forex += f'<div class="currency-column">'
        
        # 1. PILE VERTE
        for item in winners:
            bg = get_color(item['pct'])
            html_forex += f'<div class="tile" style="background:{bg}"><span class="pair">{item["other"]}</span><span class="val">+{item["pct"]:.2f}%</span></div>'
            
        # 2. SÉPARATEUR (NOM DEVISE)
        html_forex += f'<div class="separator">{curr}</div>'

        # 3. PILE GRISE
        for item in unchanged:
             html_forex += f'<div class="tile" style="background:#555"><span class="pair">{item["other"]}</span><span class="val">unch</span></div>'
        
        # 4. PILE ROUGE
        for item in losers:
            bg = get_color(item['pct'])
            html_forex += f'<div class="tile" style="background:{bg}"><span class="pair">{item["other"]}</span><span class="val">{item["pct"]:.2f}%</span></div>'
            
        html_forex += '</div>' # Fin colonne
        
    html_forex += '</div>'

    # --- AUTRES ACTIFS ---
    def make_grid(cat):
        sub = df[df['cat'] == cat].sort_values(by='pct', ascending=False)
        h = '<div class="grid-container">'
        for _, r in sub.iterrows():
            bg = get_color(r['pct'])
            h += f'<div class="box" style="background:{bg}">{r["name"]}<br><span class="val">{r["pct"]:+.2f}%</span></div>'
        h += '</div>'
        return h

    html_indices = make_grid('INDICES')
    html_commo = make_grid('COMMODITIES')

    # --- CSS COMPLET (INJECTÉ DANS L'IFRAME) ---
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ font-family: -apple-system, sans-serif; background-color: transparent; color: white; margin: 0; padding: 10px; }}
        
        /* CONTENEUR PRINCIPAL HORIZONTAL (SCROLLABLE) */
        .matrix-container {{
            display: flex;
            flex-direction: row; /* C'EST CA LA CLÉ : CÔTE À CÔTE */
            flex-wrap: nowrap;   /* INTERDICTION DE PASSER À LA LIGNE */
            gap: 10px;
            overflow-x: auto;
            align-items: flex-start; /* Tout aligné en haut */
            padding-bottom: 20px;
        }}
        
        /* UNE COLONNE (VERTICALE) */
        .currency-column {{
            display: flex;
            flex-direction: column; /* Les tuiles s'empilent DANS la colonne */
            min-width: 125px;       /* Largeur fixe comme Barchart */
            max-width: 125px;
        }}

        /* LA TUILE FOREX */
        .tile {{
            display: flex;
            justify-content: space-between;
            padding: 4px 8px;
            margin-bottom: 1px;
            font-size: 11px;
            font-weight: bold;
            color: white;
            border-radius: 1px;
        }}
        
        /* LE SÉPARATEUR CENTRAL */
        .separator {{
            background-color: #f0f0f0;
            color: #222;
            font-weight: 900;
            padding: 5px;
            margin: 3px 0;
            font-size: 13px;
        }}
        
        .val {{ font-family: monospace; }}
        
        /* SECTION TITRES */
        h3 {{ color: #aaa; border-bottom: 1px solid #444; padding-bottom: 5px; margin-top: 30px; font-size: 16px; }}
        
        /* INDICES & COMMO (GRILLE) */
        .grid-container {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .box {{ width: 100px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center; font-size: 11px; font-weight: bold; color: white; border-radius: 4px; text-align: center; }}
        
        /* SCROLLBAR PROPRE */
        ::-webkit-scrollbar {{ height: 8px; }}
        ::-webkit-scrollbar-track {{ background: #222; }}
        ::-webkit-scrollbar-thumb {{ background: #555; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #777; }}
    </style>
    </head>
    <body>
        <h3>💱 FOREX MARKET MAP</h3>
        {html_forex}
        
        <h3>📊 INDICES</h3>
        {html_indices}
        
        <h3>🪙 COMMODITIES</h3>
        {html_commo}
    </body>
    </html>
    """
    return full_html

# ------------------------------------------------------------
# 3. APP PRINCIPALE
# ------------------------------------------------------------
st.title("🗺️ Market Map Pro (Barchart Replica)")

with st.sidebar:
    st.header("Réglages")
    CONFIG['lookback_days'] = st.slider("Jours", 1, 30, 1)
    if st.secrets.get("OANDA_ACCOUNT_ID"): st.success("OANDA: OK")

if st.button("🚀 ACTUALISER", type="primary"):
    df_res = get_market_data(CONFIG)
    if not df_res.empty:
        html_code = generate_report(df_res)
        st.components.v1.html(html_code, height=1000, scrolling=True)
    else:
        st.error("Aucune donnée.")
