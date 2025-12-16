import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Market Map Pro", layout="wide")

# ------------------------------------------------------------
# 1. CONFIGURATION ÉPURÉE
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
        'INDICES': ['US30_USD', 'NAS100_USD', 'SPX500_USD', 'DE30_EUR'],
        'COMMODITIES': ['XAU_USD', 'XPT_USD', 'XAG_USD']
    },
    'lookback_days': 1
}

DISPLAY_NAMES = {
    'US30_USD': 'DOW JONES', 'NAS100_USD': 'NASDAQ 100', 'SPX500_USD': 'S&P 500', 
    'DE30_EUR': 'DAX 40', 'XAU_USD': 'GOLD', 'XPT_USD': 'PLATINUM', 'XAG_USD': 'SILVER'
}

# ------------------------------------------------------------
# 2. DATA ENGINE
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
# 3. MOTEUR GRAPHIQUE INTELLIGENT
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
    
    # --- ALGORITHME "SMART WEIGHTED SCORE" ---
    # Objectif : Trier les colonnes (devises) comme Barchart
    currency_scores = {}
    
    for curr, items in data.items():
        score = 0
        valid_items = 0
        
        for item in items:
            opponent = item['other']
            val = item['pct']
            
            # PONDÉRATION :
            # Si on gagne contre USD, EUR ou JPY, ça compte DOUBLE.
            # C'est la logique "Weighted" adaptée au sentiment de marché.
            weight = 2.0 if opponent in ['USD', 'EUR', 'JPY'] else 1.0
            
            score += (val * weight)
            valid_items += weight
            
        # Score final normalisé
        final_score = score / valid_items if valid_items > 0 else 0
        currency_scores[curr] = final_score

    # Tri basé sur ce score intelligent
    sorted_currencies = sorted(currency_scores, key=currency_scores.get, reverse=True)

    # --- GÉNÉRATION HTML ---
    html_forex = '<div class="matrix-container">'
    for curr in sorted_currencies:
        items = data[curr]
        winners = [x for x in items if x['pct'] >= 0.005]
        losers = [x for x in items if x['pct'] < -0.005]
        unchanged = [x for x in items if -0.005 <= x['pct'] < 0.005]
        
        # Tri interne des piles (Magnitude simple)
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

    def make_grid(cat):
        sub = df[df['cat'] == cat].sort_values(by='pct', ascending=False)
        if sub.empty: return ""
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

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ font-family: -apple-system, sans-serif; background-color: transparent; color: white; margin: 0; padding: 10px; }}
        
        .matrix-container {{
            display: flex; flex-direction: row; flex-wrap: nowrap;
            gap: 10px; overflow-x: auto; align-items: flex-start; padding-bottom: 20px;
        }}
        .currency-column {{ display: flex; flex-direction: column; min-width: 125px; max-width: 125px; }}
        .tile {{ display: flex; justify-content: space-between; padding: 4px 8px; margin-bottom: 1px; font-size: 11px; font-weight: bold; color: white; border-radius: 1px; }}
        .separator {{ background-color: #f0f0f0; color: #222; font-weight: 900; padding: 5px; margin: 3px 0; font-size: 13px; text-transform: uppercase; }}
        
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
        <h3>💱 FOREX MAP</h3>
        {html_forex}
        <h3>📊 INDICES</h3>
        {html_indices}
        <h3>🪙 METAUX</h3>
        {html_commo}
    </body>
    </html>
    """
    return full_html

# ------------------------------------------------------------
# 4. APP SIMPLE
# ------------------------------------------------------------
st.title("🗺️ Market Map Pro")

with st.sidebar:
    st.header("Réglages")
    CONFIG['lookback_days'] = st.slider("Période", 1, 5, 1)

if st.button("🚀 ACTUALISER", type="primary"):
    df_res = get_market_data(CONFIG)
    if not df_res.empty:
        html_code = generate_report(df_res)
        st.components.v1.html(html_code, height=1000, scrolling=True)
    else:
        st.error("Erreur de données.")
