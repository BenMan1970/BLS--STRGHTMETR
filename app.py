import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import zscore
import requests
from datetime import datetime, timedelta

# ------------------------------------------------------------
# 1. STYLE CSS (DESIGN TUILES)
# ------------------------------------------------------------
st.set_page_config(page_title="Market Heatmap Pro", layout="wide")

st.markdown("""
<style>
    /* Fond sombre global */
    .stApp { background-color: #0e1117; }

    /* CONTENEUR PRINCIPAL FLEXBOX (Pour aligner les tuiles) */
    .heatmap-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: flex-start;
        padding: 10px 0;
        width: 100%;
    }

    /* LA TUILE (Carte rectangulaire) */
    .market-tile {
        display: inline-flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        width: 120px;
        height: 70px;
        border-radius: 6px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        border: 1px solid rgba(255,255,255,0.08);
        transition: transform 0.2s;
    }
    
    .market-tile:hover {
        transform: translateY(-3px);
        border-color: rgba(255,255,255,0.5);
        cursor: pointer;
    }

    /* Texte SYMBOLE (ex: EURUSD) */
    .tile-symbol {
        font-family: 'Arial', sans-serif;
        font-weight: 800;
        font-size: 14px;
        margin-bottom: 4px;
        text-shadow: 0 1px 2px rgba(0,0,0,0.8);
    }
    
    /* Texte SCORE (ex: 7.8) */
    .tile-score {
        font-family: 'Courier New', monospace;
        font-weight: bold;
        font-size: 15px;
        background-color: rgba(0,0,0,0.3);
        padding: 2px 8px;
        border-radius: 4px;
    }

    /* TITRES DES SECTIONS */
    .section-header {
        font-family: 'Helvetica', sans-serif;
        font-size: 18px;
        font-weight: 600;
        color: #8b949e;
        margin-top: 25px;
        margin-bottom: 10px;
        border-bottom: 1px solid #30363d;
        padding-bottom: 5px;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 2. CONFIGURATION DES ACTIFS
# ------------------------------------------------------------
CONFIG = {
    'instruments': [
        # FOREX (format OANDA)
        'EUR_USD', 'GBP_USD', 'USD_JPY', 'USD_CHF', 'AUD_USD', 'USD_CAD', 'NZD_USD',
        'EUR_GBP', 'EUR_JPY', 'EUR_CHF', 'EUR_AUD', 'EUR_CAD', 'EUR_NZD',
        'GBP_JPY', 'GBP_CHF', 'GBP_AUD', 'GBP_CAD', 'GBP_NZD',
        'AUD_JPY', 'AUD_CAD', 'AUD_NZD', 'AUD_CHF',
        'CAD_JPY', 'CAD_CHF', 'NZD_JPY', 'NZD_CHF', 'CHF_JPY'
    ],
    'lookback_days': 3,
    'atr_period': 14
}

# ------------------------------------------------------------
# 3. CONNEXION OANDA
# ------------------------------------------------------------
def get_oanda_credentials():
    """Récupère les credentials OANDA depuis les secrets"""
    try:
        account_id = st.secrets["OANDA_ACCOUNT_ID"]
        access_token = st.secrets["OANDA_ACCESS_TOKEN"]
        return account_id, access_token
    except:
        return None, None

def fetch_oanda_candles(instrument, count=60):
    """Récupère les données OANDA pour un instrument"""
    account_id, access_token = get_oanda_credentials()
    
    if not account_id or not access_token:
        return None
    
    # URL de l'API OANDA (practice ou live)
    base_url = "https://api-fxpractice.oanda.com"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    params = {
        "count": count,
        "granularity": "D"  # Daily candles
    }
    
    try:
        url = f"{base_url}/v3/instruments/{instrument}/candles"
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            candles = data.get('candles', [])
            
            if not candles:
                return None
            
            # Conversion en DataFrame
            df = pd.DataFrame([{
                'time': c['time'],
                'open': float(c['mid']['o']),
                'high': float(c['mid']['h']),
                'low': float(c['mid']['l']),
                'close': float(c['mid']['c']),
                'volume': int(c['volume'])
            } for c in candles if c['complete']])
            
            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time')
            df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
            
            return df
        else:
            return None
    except Exception as e:
        return None

# ------------------------------------------------------------
# 4. MOTEUR DE CALCUL (DATA)
# ------------------------------------------------------------
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

def get_market_data(config):
    instruments = config['instruments']
    results = {}
    
    progress_bar = st.progress(0)
    status = st.empty()
    
    for idx, instrument in enumerate(instruments):
        status.text(f"📊 Analyse {instrument}...")
        
        try:
            df = fetch_oanda_candles(instrument, count=60)
            
            if df is None or len(df) < 20:
                continue
            
            close = df['Close']
            price_now = close.iloc[-1]
            price_past = close.shift(config['lookback_days']).iloc[-1]
            
            if pd.isna(price_now) or pd.isna(price_past) or price_past == 0:
                continue

            # Calculs
            raw_move_pct = (price_now - price_past) / price_past
            atr = calculate_atr(df, config['atr_period']).iloc[-1]
            atr_pct = (atr / price_now) if price_now != 0 else 0.001
            strength = raw_move_pct / max(atr_pct, 0.0001)
            
            # Nettoyage du nom
            display_name = instrument.replace('_', '')

            results[instrument] = {
                'name': display_name,
                'raw_score': strength,
                'pct_change': raw_move_pct * 100,
                'category': 'FOREX'
            }
            
        except Exception as e:
            continue
        
        progress_bar.progress((idx + 1) / len(instruments))
    
    progress_bar.empty()
    status.empty()

    if not results:
        return pd.DataFrame()

    df_res = pd.DataFrame.from_dict(results, orient='index')
    
    # Tri par variation % (du plus positif au plus négatif)
    return df_res.sort_values(by='pct_change', ascending=False)

# ------------------------------------------------------------
# 5. GÉNÉRATEUR HTML
# ------------------------------------------------------------
def get_color(pct_change):
    """Palette de couleurs basée sur la variation % réelle"""
    # Vert (positif)
    if pct_change >= 0.50: return "#064e3b"
    if pct_change >= 0.30: return "#15803d"
    if pct_change >= 0.15: return "#22c55e"
    if pct_change >= 0.05: return "#4ade80"
    if pct_change >= 0.01: return "#86efac"
    
    # Rouge (négatif)
    if pct_change <= -0.50: return "#7f1d1d"
    if pct_change <= -0.30: return "#b91c1c"
    if pct_change <= -0.15: return "#ef4444"
    if pct_change <= -0.05: return "#f87171"
    if pct_change <= -0.01: return "#fca5a5"
    
    return "#4b5563"

def generate_full_html_report(df):
    """Génère le HTML complet"""
    if df.empty:
        return "<div style='color:red'>Aucune donnée.</div>"
    
    tiles_html = f'<div class="section-header">💱 FOREX (Paires Majeures & Croisées)</div>'
    tiles_html += '<div class="heatmap-container">'
    
    for _, row in df.iterrows():
        pct_change = row['pct_change']
        name = row['name']
        bg_color = get_color(pct_change)
        
        tiles_html += f'''
        <div class="market-tile" style="background-color: {bg_color};">
            <div class="tile-symbol">{name}</div>
            <div class="tile-score">{pct_change:+.2f}%</div>
        </div>
        '''
    
    tiles_html += '</div>'
    return tiles_html

# ------------------------------------------------------------
# 6. APPLICATION STREAMLIT
# ------------------------------------------------------------
st.title("🗺️ Market Heatmap Pro")
st.write("Variations du marché en temps réel via OANDA. Vert = Hausse | Rouge = Baisse")

# Options dans la sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    lookback = st.slider("Période d'analyse (jours)", 1, 10, CONFIG['lookback_days'])
    CONFIG['lookback_days'] = lookback
    
    atr_period = st.slider("Période ATR", 5, 30, CONFIG['atr_period'])
    CONFIG['atr_period'] = atr_period
    
    st.markdown("---")
    
    # Vérification de la connexion OANDA
    account_id, access_token = get_oanda_credentials()
    if account_id and access_token:
        st.success("✅ OANDA connecté")
        st.caption(f"Compte: {account_id[:8]}...")
    else:
        st.error("❌ OANDA non configuré")
        st.caption("Ajoutez vos credentials dans les Secrets")

if st.button("🚀 SCANNER LE MARCHÉ", type="primary"):
    # Vérifier la connexion OANDA
    if get_oanda_credentials()[0] is None:
        st.error("❌ Configuration OANDA manquante. Ajoutez vos credentials dans les Secrets.")
    else:
        with st.spinner("Téléchargement des données OANDA..."):
            # Calculs
            df_results = get_market_data(CONFIG)
            
            if not df_results.empty:
                st.metric("📊 Paires analysées", len(df_results))
                
                # Génération et affichage du HTML
                html_content = generate_full_html_report(df_results)
                
                st.components.v1.html(
                    f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <style>
                            body {{
                                margin: 0;
                                padding: 0;
                                background-color: transparent;
                                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            }}
                            .heatmap-container {{
                                display: flex;
                                flex-wrap: wrap;
                                gap: 8px;
                                justify-content: flex-start;
                                padding: 10px 0;
                                width: 100%;
                            }}
                            .market-tile {{
                                display: inline-flex;
                                flex-direction: column;
                                justify-content: center;
                                align-items: center;
                                width: 120px;
                                height: 70px;
                                border-radius: 6px;
                                color: white;
                                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                                border: 1px solid rgba(255,255,255,0.08);
                                transition: transform 0.2s;
                            }}
                            .market-tile:hover {{
                                transform: translateY(-3px);
                                border-color: rgba(255,255,255,0.5);
                                cursor: pointer;
                            }}
                            .tile-symbol {{
                                font-family: 'Arial', sans-serif;
                                font-weight: 800;
                                font-size: 14px;
                                margin-bottom: 4px;
                                text-shadow: 0 1px 2px rgba(0,0,0,0.8);
                            }}
                            .tile-score {{
                                font-family: 'Courier New', monospace;
                                font-weight: bold;
                                font-size: 15px;
                                background-color: rgba(0,0,0,0.3);
                                padding: 2px 8px;
                                border-radius: 4px;
                            }}
                            .section-header {{
                                font-family: 'Helvetica', sans-serif;
                                font-size: 18px;
                                font-weight: 600;
                                color: #8b949e;
                                margin-top: 25px;
                                margin-bottom: 10px;
                                border-bottom: 1px solid #30363d;
                                padding-bottom: 5px;
                                width: 100%;
                            }}
                        </style>
                    </head>
                    <body>
                        {html_content}
                    </body>
                    </html>
                    """,
                    height=800,
                    scrolling=True
                )
                
            else:
                st.error("Aucune donnée récupérée. Vérifiez votre connexion OANDA.")

else:
    st.info("👆 Cliquez pour lancer l'analyse des paires Forex via OANDA")
