import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Market Map Pro", layout="wide")

# ------------------------------------------------------------
# 1. CONFIGURATION FILTRÉE (UNIQUEMENT CE QUE VOUS VOULEZ)
# ------------------------------------------------------------
CONFIG = {
    'instruments': {
        'FOREX': [
            # On garde tout le Forex pour que la matrice fonctionne bien
            'EUR_USD', 'GBP_USD', 'USD_JPY', 'USD_CHF', 'AUD_USD', 'USD_CAD', 'NZD_USD',
            'EUR_GBP', 'EUR_JPY', 'EUR_CHF', 'EUR_AUD', 'EUR_CAD', 'EUR_NZD',
            'GBP_JPY', 'GBP_CHF', 'GBP_AUD', 'GBP_CAD', 'GBP_NZD',
            'AUD_JPY', 'AUD_CAD', 'AUD_NZD', 'AUD_CHF',
            'CAD_JPY', 'CAD_CHF', 'NZD_JPY', 'NZD_CHF', 'CHF_JPY'
        ],
        'INDICES': [
            'US30_USD',    # Dow Jones
            'NAS100_USD',  # Nasdaq
            'SPX500_USD',  # S&P 500
            'DE30_EUR'     # DAX
        ],
        'COMMODITIES': [
            'XAU_USD',     # Gold
            'XPT_USD',     # Platinum
            'XAG_USD'      # Silver
        ]
    },
    'lookback_days': 1
}

# Noms d'affichage propres
DISPLAY_NAMES = {
    'US30_USD': 'DOW JONES',
    'NAS100_USD': 'NASDAQ 100',
    'SPX500_USD': 'S&P 500',
    'DE30_EUR': 'DAX 40',
    'XAU_USD': 'GOLD',
    'XPT_USD': 'PLATINUM',
    'XAG_USD': 'SILVER'
}

# ------------------------------------------------------------
# 2. MOTEUR DE DONNÉES (INVISIBLE)
# ------------------------------------------------------------
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
    
    # Barre de progression discrète
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
# 3. GÉNÉRATEUR HTML/CSS
# ------------------------------------------------------------
def get_color(pct):
    if pct >= 0.50: return "#004d00" 
    if pct >= 0.25: return "#006400"
    if pct >= 0.10: return "#008000"
    if pct >= 0.01: return "#00a000" 
    
    if pct <= -0.50: return "#8b0000" 
    if pct <= -0.25: return "#a00000"
    if pct <= -0.10: return "#b00000"
    if pct <= -0.01: return "#cc0000" 
    
    return "#555"

def generate_report(df):
    forex_df = df[df['cat'] == 'FOREX']
    
    # --- LOGIQUE MATRIX FOREX ---
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
    
    currency_scores = {curr: sum(d['pct'] for d in items)/len(items) for curr, items in data.items()}
    sorted_currencies = sorted(currency_scores, key=currency_scores.get, reverse=True)

    html_forex = '<div class="matrix-container">'
    for curr in sorted_currencies:
        items = data[curr]
        winners = [x for x in items if x['pct'] >= 0.005]
        losers = [x for x in items if x['pct'] < -0.005]
        unchanged = [x for x in items if -0.005 <= x['pct'] < 0.005]
        
        winners.sort(key=lambda x: x['pct'], reverse=True) 
        losers.sort(key=lambda x: x['pct'], reverse=True)
        
        html_forex += f'<div class="currency-column">'
        for item in winners:
            bg = get_color(item['pct'])
            html_forex += f'<div class="tile" style="background:{bg}"><span class="pair">{item["other"]}</span><span class="val">+{item["pct"]:.2f}%</span></div>'
            
        html_forex += f'<div class="separator">{curr}</div>'

        for item in unchanged:
             html_forex += f'<div class="tile" style="background:#555"><span class="pair">{item["other"]}</span><span class="val">unch</span></div>'
        
        for item in losers:
            bg = get_color(item['pct'])
            html_forex += f'<div class="tile" style="background:{bg}"><span class="pair">{item["other"]}</span><span class="val">{item["pct"]:.2f}%</span></div>'
        html_forex += '</div>'
    html_forex += '</div>'

    # --- LOGIQUE INDICES ET COMMODITIES (SIMPLIFIÉE) ---
    def make_grid(cat):
        sub = df[df['cat'] == cat].sort_values(by='pct', ascending=False)
        if sub.empty: return "<div style='color:#666'>Données indisponibles</div>"
        
        h = '<div class="grid-container">'
        for _, r in sub.iterrows():
            bg = get_color(r['pct'])
            h += f'''
            <div class="box" style="background:{bg}">
                <div style="font-size:12px; margin-bottom:5px;">{r["name"]}</div>
                <div class="val" style="font-size:14px;">{r["pct"]:+.2f}%</div>
            </div>
            '''
        h += '</div>'
        return h

    html_indices = make_grid('INDICES')
    html_commo = make_grid('COMMODITIES')

    # --- CSS COMPLET ---
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ font-family: -apple-system, sans-serif; background-color: transparent; color: white; margin: 0; padding: 10px; }}
        
        /* FOREX MATRIX (Horizontal Scroll) */
        .matrix-container {{
            display: flex; flex-direction: row; flex-wrap: nowrap;
            gap: 10px; overflow-x: auto; align-items: flex-start; padding-bottom: 20px;
        }}
        .currency-column {{ display: flex; flex-direction: column; min-width: 125px; max-width: 125px; }}
        .tile {{ display: flex; justify-content: space-between; padding: 4px 8px; margin-bottom: 1px; font-size: 11px; font-weight: bold; color: white; border-radius: 1px; }}
        .separator {{ background-color: #f0f0f0; color: #222; font-weight: 900; padding: 5px; margin: 3px 0; font-size: 13px; text-transform: uppercase; }}
        
        /* GRIDS (INDICES/COMMO) */
        .grid-container {{ display: flex; flex-wrap: wrap; gap: 10px; }}
        .box {{ 
            width: 130px; height: 70px; 
            display: flex; flex-direction: column; justify-content: center; align-items: center; 
            font-weight: bold; color: white; border-radius: 4px; text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }}
        
        .val {{ font-family: monospace; }}
        h3 {{ color: #aaa; border-bottom: 1px solid #444; padding-bottom: 5px; margin-top: 30px; font-size: 16px; font-family: Helvetica, sans-serif; }}
        
        ::-webkit-scrollbar {{ height: 8px; }}
        ::-webkit-scrollbar-track {{ background: #222; }}
        ::-webkit-scrollbar-thumb {{ background: #555; border-radius: 4px; }}
    </style>
    </head>
    <body>
        <h3>💱 FOREX (Currency Strength)</h3>
        {html_forex}
        
        <h3>📊 INDICES MAJEURS</h3>
        {html_indices}
        
        <h3>🪙 METAUX PRECIEUX</h3>
        {html_commo}
    </body>
    </html>
    """
    return full_html

# ------------------------------------------------------------
# 4. APP PRINCIPALE
# ------------------------------------------------------------
st.title("🗺️ Market Map Pro")

with st.sidebar:
    st.header("Configuration")
    CONFIG['lookback_days'] = st.slider("Période (Jours)", 1, 30, 1)
    st.caption("1 jour = Daily Change")

if st.button("🚀 ACTUALISER", type="primary"):
    df_res = get_market_data(CONFIG)
    if not df_res.empty:
        html_code = generate_report(df_res)
        st.components.v1.html(html_code, height=1000, scrolling=True)
    else:
        st.error("Impossible de récupérer les données. Vérifiez la connexion API.")
