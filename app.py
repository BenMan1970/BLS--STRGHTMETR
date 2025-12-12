import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
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
    
    /* Badge de source de données */
    .data-source-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
        margin-bottom: 10px;
    }
    
    .source-oanda {
        background-color: #15803d;
        color: white;
    }
    
    .source-yahoo {
        background-color: #4b5563;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 2. CONFIGURATION DES ACTIFS
# ------------------------------------------------------------
CONFIG = {
    'tickers': [
        # FOREX
        'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'AUDUSD=X', 'USDCAD=X', 'NZDUSD=X',
        'EURGBP=X', 'EURJPY=X', 'EURCHF=X', 'EURAUD=X', 'EURCAD=X', 'EURNZD=X',
        'GBPJPY=X', 'GBPCHF=X', 'GBPAUD=X', 'GBPCAD=X', 'GBPNZD=X',
        'AUDJPY=X', 'AUDCAD=X', 'AUDNZD=X', 'AUDCHF=X',
        'CADJPY=X', 'CADCHF=X', 'NZDJPY=X', 'NZDCHF=X', 'CHFJPY=X',
        # INDICES
        '^DJI', '^GSPC', '^IXIC', '^FCHI', '^GDAXI',
        # MATIÈRES PREMIÈRES
        'GC=F', 'CL=F', 'SI=F', 'HG=F'
    ],
    'period': '60d', 'interval': '1d', 'lookback_days': 3, 'atr_period': 14
}

# Mapping Yahoo -> OANDA pour les paires Forex
YAHOO_TO_OANDA = {
    'EURUSD=X': 'EUR_USD', 'GBPUSD=X': 'GBP_USD', 'USDJPY=X': 'USD_JPY',
    'USDCHF=X': 'USD_CHF', 'AUDUSD=X': 'AUD_USD', 'USDCAD=X': 'USD_CAD',
    'NZDUSD=X': 'NZD_USD', 'EURGBP=X': 'EUR_GBP', 'EURJPY=X': 'EUR_JPY',
    'EURCHF=X': 'EUR_CHF', 'EURAUD=X': 'EUR_AUD', 'EURCAD=X': 'EUR_CAD',
    'EURNZD=X': 'EUR_NZD', 'GBPJPY=X': 'GBP_JPY', 'GBPCHF=X': 'GBP_CHF',
    'GBPAUD=X': 'GBP_AUD', 'GBPCAD=X': 'GBP_CAD', 'GBPNZD=X': 'GBP_NZD',
    'AUDJPY=X': 'AUD_JPY', 'AUDCAD=X': 'AUD_CAD', 'AUDNZD=X': 'AUD_NZD',
    'AUDCHF=X': 'AUD_CHF', 'CADJPY=X': 'CAD_JPY', 'CADCHF=X': 'CAD_CHF',
    'NZDJPY=X': 'NZD_JPY', 'NZDCHF=X': 'NZD_CHF', 'CHFJPY=X': 'CHF_JPY'
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
    base_url = "https://api-fxpractice.oanda.com"  # Changez en https://api-fxtrade.oanda.com pour le compte réel
    
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
        st.warning(f"Erreur OANDA pour {instrument}: {str(e)}")
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

def get_market_data(config, use_oanda=True):
    tickers = config['tickers']
    results = {}
    data_sources = {}
    
    # Vérifier si OANDA est disponible
    oanda_available = use_oanda and get_oanda_credentials()[0] is not None
    
    if oanda_available:
        st.info("🟢 Connexion OANDA active - Données en temps réel")
    else:
        st.info("📊 Utilisation de Yahoo Finance")
    
    # Téléchargement Yahoo Finance pour tous les actifs
    data = yf.download(tickers, period=config['period'], interval=config['interval'], group_by='ticker', progress=False)
    
    for ticker in tickers:
        try:
            # Essayer OANDA d'abord pour les paires Forex
            df = None
            source = "Yahoo"
            
            if oanda_available and ticker in YAHOO_TO_OANDA:
                oanda_instrument = YAHOO_TO_OANDA[ticker]
                df = fetch_oanda_candles(oanda_instrument, count=60)
                if df is not None and len(df) >= 20:
                    source = "OANDA"
            
            # Fallback sur Yahoo Finance si OANDA échoue
            if df is None:
                df = data[ticker].dropna()
                if len(df) < 20:
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
            
            # Catégories
            if "=X" in ticker:
                cat = "FOREX"
            elif "=F" in ticker:
                cat = "COMMODITIES"
            elif "^" in ticker:
                cat = "INDICES"
            else:
                cat = "OTHER"
            
            # Nettoyage des noms
            display_name = ticker.replace('=X','').replace('=F','').replace('^','')
            mapping = {
                'DJI':'US30', 'GSPC':'SPX500', 'IXIC':'NAS100', 
                'FCHI':'CAC40', 'GDAXI':'DAX', 'GC':'GOLD', 
                'CL':'OIL', 'SI':'SILVER', 'HG':'COPPER'
            }
            display_name = mapping.get(display_name, display_name)

            results[ticker] = {
                'name': display_name,
                'raw_score': strength,
                'category': cat
            }
            data_sources[ticker] = source
            
        except KeyError:
            continue
        except Exception as e:
            st.warning(f"Erreur pour {ticker}: {str(e)}")
            continue

    if not results:
        return pd.DataFrame(), {}

    df_res = pd.DataFrame.from_dict(results, orient='index')
    
    # Normalisation sur 0-10
    vals = df_res['raw_score'].values
    z = zscore(vals)
    z = np.clip(np.nan_to_num(z), -2.5, 2.5)
    df_res['score'] = 5 + (z / 5) * 10
    df_res['score'] = df_res['score'].clip(0, 10)
    
    return df_res.sort_values(by='score', ascending=False), data_sources

# ------------------------------------------------------------
# 5. GÉNÉRATEUR HTML (LOGIQUE CORRIGÉE)
# ------------------------------------------------------------
def get_color(score):
    # Palette Finviz: Vert Foncé (Achat Fort) -> Rouge Foncé (Vente Forte)
    if score >= 8.5: return "#064e3b" # Vert Foncé
    if score >= 7.0: return "#15803d" # Vert
    if score >= 6.0: return "#22c55e" # Vert Clair
    if score >= 5.5: return "#4b5563" # Gris-Vert
    
    if score <= 1.5: return "#7f1d1d" # Rouge Foncé
    if score <= 3.0: return "#b91c1c" # Rouge
    if score <= 4.0: return "#ef4444" # Rouge Clair
    if score <= 4.5: return "#4b5563" # Gris-Rouge
    
    return "#374151" # Gris Neutre

def generate_full_html_report(df):
    """
    Génère le HTML complet avec toutes les sections dans un seul bloc
    """
    if df.empty: return "<div style='color:red'>Aucune donnée.</div>"
    
    # Définition des sections
    sections = [
        ("💱 FOREX (Paires Majeures & Croisées)", 'FOREX'),
        ("📊 INDICES MONDIAUX", 'INDICES'),
        ("🪙 MATIÈRES PREMIÈRES", 'COMMODITIES')
    ]
    
    # Construction du HTML en une seule fois
    tiles_html = ""
    
    for title, cat_key in sections:
        subset = df[df['category'] == cat_key]
        if subset.empty: continue
        
        # Ajouter le titre de section
        tiles_html += f'<div class="section-header">{title}</div>'
        
        # Ouvrir le conteneur
        tiles_html += '<div class="heatmap-container">'
        
        # Ajouter toutes les tuiles
        for _, row in subset.iterrows():
            score = row['score']
            name = row['name']
            bg_color = get_color(score)
            
            tiles_html += f'''
            <div class="market-tile" style="background-color: {bg_color};">
                <div class="tile-symbol">{name}</div>
                <div class="tile-score">{score:.1f}</div>
            </div>
            '''
        
        # Fermer le conteneur
        tiles_html += '</div>'
    
    return tiles_html

# ------------------------------------------------------------
# 6. APPLICATION STREAMLIT
# ------------------------------------------------------------
st.title("🗺️ Market Heatmap Pro")
st.write("Analyse de force relative. Vert = Acheteur | Rouge = Vendeur.")

# Options dans la sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    use_oanda = st.checkbox("Utiliser OANDA API", value=True, 
                            help="Utilise l'API OANDA pour des données Forex en temps réel")
    
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
        st.warning("⚠️ OANDA non configuré")
        st.caption("Ajoutez vos credentials dans les Secrets")

if st.button("🚀 SCANNER LE MARCHÉ", type="primary"):
    with st.spinner("Téléchargement et calculs en cours..."):
        # 1. Calculs
        df_results, sources = get_market_data(CONFIG, use_oanda=use_oanda)
        
        if not df_results.empty:
            # Afficher les statistiques de sources
            oanda_count = sum(1 for s in sources.values() if s == "OANDA")
            yahoo_count = len(sources) - oanda_count
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Total actifs", len(sources))
            with col2:
                st.metric("🟢 OANDA", oanda_count)
            with col3:
                st.metric("📈 Yahoo Finance", yahoo_count)
            
            # 2. Génération et affichage du HTML
            html_content = generate_full_html_report(df_results)
            
            # 3. Affichage avec components.html pour un meilleur rendu
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
            st.error("Erreur de récupération des données. Vérifiez votre connexion.")

else:
    st.info("Cliquez sur le bouton pour lancer l'analyse.")
