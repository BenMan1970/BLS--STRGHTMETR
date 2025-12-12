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
# 2. CONFIGURATION DES ACTIFS (100% OANDA)
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
            'SPX500_USD',  # S&P 500
            'NAS100_USD',  # NASDAQ 100
            'US30_USD',    # Dow Jones
            'DE30_EUR',    # DAX
            'FR40_EUR',    # CAC 40
            'UK100_GBP',   # FTSE 100
            'JP225_USD',   # Nikkei 225
            'AUS200_AUD',  # ASX 200
            'HK33_HKD'     # Hang Seng
        ],
        'COMMODITIES': [
            'XAU_USD',     # Gold
            'XAG_USD',     # Silver
            'XPT_USD',     # Platinum
            'XPD_USD',     # Palladium
            'BCO_USD',     # Brent Crude Oil
            'WTICO_USD',   # WTI Crude Oil
            'NATGAS_USD',  # Natural Gas
            'CORN_USD',    # Corn
            'WHEAT_USD',   # Wheat
            'SOYBN_USD',   # Soybeans
            'SUGAR_USD',   # Sugar
            'XCU_USD'      # Copper
        ]
    },
    'lookback_days': 3,
    'atr_period': 14
}

# Mapping pour les noms d'affichage
DISPLAY_NAMES = {
    'SPX500_USD': 'SPX500', 'NAS100_USD': 'NAS100', 'US30_USD': 'US30',
    'DE30_EUR': 'DAX', 'FR40_EUR': 'CAC40', 'UK100_GBP': 'FTSE100',
    'JP225_USD': 'NIKKEI', 'AUS200_AUD': 'ASX200', 'HK33_HKD': 'HANGSENG',
    'XAU_USD': 'GOLD', 'XAG_USD': 'SILVER', 'XPT_USD': 'PLATINUM',
    'XPD_USD': 'PALLADIUM', 'BCO_USD': 'BRENT', 'WTICO_USD': 'WTI',
    'NATGAS_USD': 'NATGAS', 'CORN_USD': 'CORN', 'WHEAT_USD': 'WHEAT',
    'SOYBN_USD': 'SOYBEAN', 'SUGAR_USD': 'SUGAR', 'XCU_USD': 'COPPER'
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
    
    base_url = "https://api-fxpractice.oanda.com"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    params = {
        "count": count,
        "granularity": "D"
    }
    
    try:
        url = f"{base_url}/v3/instruments/{instrument}/candles"
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            candles = data.get('candles', [])
            
            if not candles:
                return None
            
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
    results = {}
    
    # Vérifier si OANDA est disponible
    oanda_available = get_oanda_credentials()[0] is not None
    
    if not oanda_available:
        st.error("❌ Configuration OANDA manquante. Ajoutez vos credentials dans les Secrets.")
        return pd.DataFrame()
    
    # Calculer le total d'instruments
    total_instruments = sum(len(instruments) for instruments in config['instruments'].values())
    progress_bar = st.progress(0)
    status = st.empty()
    current = 0
    
    # Parcourir toutes les catégories
    for category, instruments in config['instruments'].items():
        for instrument in instruments:
            status.text(f"📊 OANDA: {instrument}...")
            
            try:
                df = fetch_oanda_candles(instrument, count=60)
                
                if df is None or len(df) < 20:
                    current += 1
                    progress_bar.progress(current / total_instruments)
                    continue
                
                close = df['Close']
                price_now = close.iloc[-1]
                price_past = close.shift(config['lookback_days']).iloc[-1]
                
                if pd.isna(price_now) or pd.isna(price_past) or price_past == 0:
                    current += 1
                    progress_bar.progress(current / total_instruments)
                    continue

                # Calculs
                raw_move_pct = (price_now - price_past) / price_past
                atr = calculate_atr(df, config['atr_period']).iloc[-1]
                atr_pct = (atr / price_now) if price_now != 0 else 0.001
                strength = raw_move_pct / max(atr_pct, 0.0001)
                
                # Nom d'affichage
                display_name = DISPLAY_NAMES.get(instrument, instrument.replace('_', ''))

                results[instrument] = {
                    'name': display_name,
                    'raw_score': strength,
                    'pct_change': raw_move_pct * 100,
                    'category': category
                }
                
            except Exception as e:
                pass
            
            current += 1
            progress_bar.progress(current / total_instruments)
    
    progress_bar.empty()
    status.empty()

    if not results:
        return pd.DataFrame()

    df_res = pd.DataFrame.from_dict(results, orient='index')
    return df_res.sort_values(by='pct_change', ascending=False)

# ------------------------------------------------------------
# 5. GÉNÉRATEUR HTML
# ------------------------------------------------------------
def get_color(pct_change):
    """Palette de couleurs basée sur la variation % réelle"""
    if pct_change >= 0.50: return "#064e3b"
    if pct_change >= 0.30: return "#15803d"
    if pct_change >= 0.15: return "#22c55e"
    if pct_change >= 0.05: return "#4ade80"
    if pct_change >= 0.01: return "#86efac"
    
    if pct_change <= -0.50: return "#7f1d1d"
    if pct_change <= -0.30: return "#b91c1c"
    if pct_change <= -0.15: return "#ef4444"
    if pct_change <= -0.05: return "#f87171"
    if pct_change <= -0.01: return "#fca5a5"
    
    return "#4b5563"

def generate_full_html_report(df):
    """Génère le HTML complet avec toutes les sections"""
    if df.empty:
        return "<div style='color:red'>Aucune donnée.</div>"
    
    sections = [
        ("💱 FOREX (Paires Majeures & Croisées)", 'FOREX'),
        ("📊 INDICES MONDIAUX", 'INDICES'),
        ("🪙 MATIÈRES PREMIÈRES & COMMODITÉS", 'COMMODITIES')
    ]
    
    tiles_html = ""
    
    for title, cat_key in sections:
        subset = df[df['category'] == cat_key]
        if subset.empty:
            continue
        
        tiles_html += f'<div class="section-header">{title}</div>'
        tiles_html += '<div class="heatmap-container">'
        
        for _, row in subset.iterrows():
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
st.write("Toutes les données en temps réel via OANDA API 🟢")

with st.sidebar:
    st.header("⚙️ Configuration")
    
    lookback = st.slider("Période d'analyse (jours)", 1, 10, CONFIG['lookback_days'])
    CONFIG['lookback_days'] = lookback
    
    atr_period = st.slider("Période ATR", 5, 30, CONFIG['atr_period'])
    CONFIG['atr_period'] = atr_period
    
    st.markdown("---")
    
    account_id, access_token = get_oanda_credentials()
    if account_id and access_token:
        st.success("✅ OANDA connecté")
        st.caption(f"Compte: {account_id[:8]}...")
    else:
        st.error("❌ OANDA non configuré")
        st.caption("Ajoutez vos credentials")
    
    st.markdown("---")
    st.info(f"""
    **Instruments disponibles:**
    - {len(CONFIG['instruments']['FOREX'])} paires Forex
    - {len(CONFIG['instruments']['INDICES'])} indices
    - {len(CONFIG['instruments']['COMMODITIES'])} commodités
    """)

if st.button("🚀 SCANNER LE MARCHÉ", type="primary"):
    with st.spinner("Téléchargement des données OANDA..."):
        df_results = get_market_data(CONFIG)
        
        if not df_results.empty:
            # Statistiques
            forex_count = len(df_results[df_results['category'] == 'FOREX'])
            indices_count = len(df_results[df_results['category'] == 'INDICES'])
            comm_count = len(df_results[df_results['category'] == 'COMMODITIES'])
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Total actifs", len(df_results))
            with col2:
                st.metric("💱 Forex", forex_count)
            with col3:
                st.metric("📈 Indices", indices_count)
            with col4:
                st.metric("🪙 Commodités", comm_count)
            
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
                height=1000,
                scrolling=True
            )
            
            st.success("✅ Analyse terminée avec succès!")
            
        else:
            st.error("Aucune donnée récupérée. Vérifiez votre configuration OANDA.")

else:
    st.info("👆 Cliquez pour scanner tous les marchés via OANDA")
