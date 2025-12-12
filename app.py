import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# ------------------------------------------------------------
# 1. STYLE CSS
# ------------------------------------------------------------
st.set_page_config(page_title="Forex Market Map", layout="wide")

st.markdown("""
<style>
    .stApp { 
        background-color: #f8f9fa;
        font-family: Arial, sans-serif;
    }
    
    .main-title {
        font-size: 28px;
        font-weight: 700;
        color: #000;
        margin-bottom: 5px;
    }
    
    .date-info {
        color: #666;
        font-size: 14px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 2. CONFIGURATION OANDA
# ------------------------------------------------------------
CURRENCIES = ['EUR', 'CAD', 'USD', 'CHF', 'NZD', 'GBP', 'JPY', 'AUD']

def get_oanda_credentials():
    """Récupère les credentials OANDA depuis les secrets"""
    try:
        account_id = st.secrets["OANDA_ACCOUNT_ID"]
        access_token = st.secrets["OANDA_ACCESS_TOKEN"]
        return account_id, access_token
    except:
        st.error("⚠️ Credentials OANDA manquants. Ajoutez-les dans les Secrets de Streamlit.")
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
                'close': float(c['mid']['c'])
            } for c in candles if c['complete']])
            
            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time')
            
            return df
        else:
            return None
    except Exception as e:
        return None

def calculate_pair_change(base, quote, lookback_days=1):
    """Calcule la variation % d'une paire"""
    instrument = f"{base}_{quote}"
    
    df = fetch_oanda_candles(instrument, count=60)
    
    if df is None or len(df) < lookback_days + 1:
        return None
    
    try:
        price_now = df['close'].iloc[-1]
        price_past = df['close'].iloc[-(lookback_days + 1)]
        
        if pd.isna(price_now) or pd.isna(price_past) or price_past == 0:
            return None
        
        pct_change = ((price_now - price_past) / price_past) * 100
        return pct_change
    except:
        return None

def get_all_pairs_data(currencies, lookback_days=1):
    """Récupère toutes les variations en forme pyramidale"""
    results = {}
    total_pairs = sum(range(1, len(currencies)))
    current = 0
    
    progress_bar = st.progress(0)
    status = st.empty()
    
    # Parcours pyramidal : chaque devise contre les suivantes
    for i, base in enumerate(currencies):
        for quote in currencies[i+1:]:
            status.text(f"📊 Analyse {base}/{quote}...")
            pct = calculate_pair_change(base, quote, lookback_days)
            results[f"{base}/{quote}"] = pct
            
            current += 1
            progress_bar.progress(current / total_pairs)
    
    progress_bar.empty()
    status.empty()
    
    return results

def get_color_from_pct(pct):
    """Couleurs basées sur le pourcentage de variation"""
    if pct is None:
        return "#e8e8e8"
    
    # Vert (positif)
    if pct >= 0.50: return "#006400"
    if pct >= 0.30: return "#228B22"
    if pct >= 0.15: return "#32CD32"
    if pct >= 0.08: return "#90EE90"
    if pct >= 0.01: return "#98FB98"
    
    # Rouge (négatif)
    if pct <= -0.50: return "#8B0000"
    if pct <= -0.30: return "#B22222"
    if pct <= -0.15: return "#DC143C"
    if pct <= -0.08: return "#FF6347"
    if pct <= -0.01: return "#FFA07A"
    
    return "#D3D3D3"

# ------------------------------------------------------------
# 3. GÉNÉRATEUR HTML DE LA PYRAMIDE
# ------------------------------------------------------------
def generate_pyramid_html(currencies, data):
    """Génère la matrice pyramidale inversée exactement comme l'image"""
    html = """
    <style>
        .pyramid-container {
            display: table;
            border-collapse: collapse;
            margin: 20px 0;
        }
        
        .pyramid-row {
            display: table-row;
        }
        
        .currency-label {
            display: table-cell;
            background-color: #e8e8e8;
            border: 1px solid #d0d0d0;
            padding: 15px;
            text-align: center;
            font-weight: 700;
            font-size: 14px;
            color: #333;
            width: 150px;
            vertical-align: middle;
        }
        
        .pair-cell {
            display: table-cell;
            border: 1px solid rgba(0,0,0,0.1);
            padding: 10px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            width: 150px;
            height: 60px;
            vertical-align: middle;
        }
        
        .pair-cell:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        .pair-name {
            font-weight: 700;
            font-size: 11px;
            margin-bottom: 4px;
            color: white;
        }
        
        .pair-value {
            font-weight: 600;
            font-size: 13px;
            color: white;
        }
    </style>
    
    <div class="pyramid-container">
    """
    
    # En-têtes des colonnes (ligne du haut)
    html += '<div class="pyramid-row">'
    html += '<div class="currency-label"></div>'
    for curr in currencies[1:]:
        html += f'<div class="currency-label">{curr}</div>'
    html += '</div>'
    
    # Lignes de données (pyramide inversée)
    for i in range(len(currencies) - 1):
        base = currencies[i]
        html += '<div class="pyramid-row">'
        
        # Label de la devise de base
        html += f'<div class="currency-label">{base}</div>'
        
        # Cellules de paires - TOUTES les colonnes
        for j in range(1, len(currencies)):
            quote = currencies[j]
            
            # Si quote vient APRÈS base dans la liste, afficher la paire
            if j > i:
                pair = f"{base}/{quote}"
                pct = data.get(pair)
                
                if pct is None:
                    html += '<div class="pair-cell" style="background-color: #e8e8e8;"><span style="color: #999; font-size: 12px;">unch</span></div>'
                else:
                    color = get_color_from_pct(pct)
                    html += f'''
                    <div class="pair-cell" style="background-color: {color};">
                        <div class="pair-name">{pair}</div>
                        <div class="pair-value">{pct:+.2f}%</div>
                    </div>
                    '''
            else:
                # Cellule vide (partie basse de la pyramide)
                html += '<div class="pair-cell" style="background-color: #e8e8e8;"></div>'
        
        html += '</div>'
    
    html += '</div>'
    return html

# ------------------------------------------------------------
# 4. APPLICATION STREAMLIT
# ------------------------------------------------------------
st.markdown('<div class="main-title">Forex Market Map</div>', unsafe_allow_html=True)

today = datetime.now().strftime("%a, %b %dth, %Y")
st.markdown(f'<div class="date-info">{today}</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Paramètres")
    
    lookback = st.slider("Période d'analyse (jours)", 1, 5, 1)
    
    st.markdown("---")
    
    # Vérification OANDA
    account_id, access_token = get_oanda_credentials()
    if account_id and access_token:
        st.success("✅ OANDA connecté")
        st.caption(f"Compte: {account_id[:8]}...")
    else:
        st.error("❌ OANDA non configuré")

# Bouton principal
if st.button("🔄 Actualiser les données", type="primary"):
    if get_oanda_credentials()[0] is None:
        st.error("❌ Impossible de continuer sans credentials OANDA. Configurez-les dans les Secrets.")
    else:
        with st.spinner("📊 Chargement des données OANDA..."):
            # Récupération des données
            data = get_all_pairs_data(CURRENCIES, lookback_days=lookback)
            
            # Génération de la pyramide
            pyramid_html = generate_pyramid_html(CURRENCIES, data)
            
            # Affichage
            st.components.v1.html(
                f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                </head>
                <body style="margin: 0; padding: 20px; background-color: #f8f9fa; font-family: Arial, sans-serif;">
                    {pyramid_html}
                </body>
                </html>
                """,
                height=650,
                scrolling=True
            )
            
            st.success("✅ Matrice mise à jour avec succès !")
            
            # Statistiques
            valid_pairs = sum(1 for v in data.values() if v is not None)
            st.info(f"📊 {valid_pairs} paires chargées depuis OANDA")

else:
    st.info("👆 Cliquez pour charger la matrice pyramidale des paires Forex")
    
    st.markdown("""
    ### 📊 Matrice Pyramidale
    
    Cette application affiche une **matrice triangulaire** des paires de devises :
    - **Forme pyramidale** : Évite les doublons (EUR/USD = inverse de USD/EUR)
    - **Données OANDA** : Prix en temps réel
    - **Couleurs** : Vert = hausse, Rouge = baisse
    
    Chaque cellule montre la performance de la devise de gauche contre celle du haut.
    """)
