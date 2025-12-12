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
    
    .matrix-grid {
        display: grid;
        grid-template-columns: 80px repeat(8, 150px);
        gap: 0;
        margin: 20px 0;
        width: fit-content;
    }
    
    .currency-header {
        background-color: #e8e8e8;
        border: 1px solid #d0d0d0;
        padding: 15px;
        text-align: center;
        font-weight: 700;
        font-size: 14px;
        color: #333;
    }
    
    .pair-cell {
        border: 1px solid rgba(0,0,0,0.1);
        padding: 10px;
        text-align: center;
        cursor: pointer;
        transition: all 0.2s;
        min-height: 60px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    
    .pair-cell:hover {
        transform: scale(1.05);
        z-index: 10;
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
    
    .empty-cell {
        background-color: #f0f0f0;
        border: 1px solid #d0d0d0;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 2. CONFIGURATION OANDA
# ------------------------------------------------------------
CURRENCIES = ['EUR', 'USD', 'CAD', 'CHF', 'NZD', 'AUD', 'JPY', 'GBP']

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
    
    # URL de l'API OANDA (practice)
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
    """Récupère toutes les variations des paires"""
    results = {}
    total = len(currencies) * len(currencies)
    current = 0
    
    progress_bar = st.progress(0)
    status = st.empty()
    
    for i, base in enumerate(currencies):
        for j, quote in enumerate(currencies):
            if base == quote:
                results[(i, j)] = None
            else:
                status.text(f"📊 Analyse {base}/{quote}...")
                pct = calculate_pair_change(base, quote, lookback_days)
                results[(i, j)] = pct
            
            current += 1
            progress_bar.progress(current / total)
    
    progress_bar.empty()
    status.empty()
    
    return results

def get_color_from_pct(pct):
    """Couleurs basées sur le pourcentage de variation"""
    if pct is None:
        return "#e8e8e8"
    
    # Vert (positif)
    if pct >= 0.50: return "#006400"    # Vert très foncé
    if pct >= 0.30: return "#228B22"    # Vert foncé
    if pct >= 0.15: return "#32CD32"    # Vert
    if pct >= 0.08: return "#90EE90"    # Vert clair
    if pct >= 0.01: return "#98FB98"    # Vert très clair
    
    # Rouge (négatif)
    if pct <= -0.50: return "#8B0000"   # Rouge très foncé
    if pct <= -0.30: return "#B22222"   # Rouge foncé
    if pct <= -0.15: return "#DC143C"   # Rouge
    if pct <= -0.08: return "#FF6347"   # Rouge clair
    if pct <= -0.01: return "#FFA07A"   # Rouge très clair
    
    return "#D3D3D3"  # Gris neutre

# ------------------------------------------------------------
# 3. GÉNÉRATEUR HTML DE LA MATRICE
# ------------------------------------------------------------
def generate_matrix_html(currencies, data):
    """Génère la matrice exactement comme l'image"""
    html = '<div class="matrix-grid">'
    
    # Première ligne : en-têtes des colonnes
    html += '<div class="currency-header"></div>'  # Coin vide
    for currency in currencies:
        html += f'<div class="currency-header">{currency}</div>'
    
    # Lignes de données
    for i, base in enumerate(currencies):
        # En-tête de ligne
        html += f'<div class="currency-header">{base}</div>'
        
        # Cellules de paires
        for j, quote in enumerate(currencies):
            if i == j:
                # Cellule diagonale
                html += f'<div class="pair-cell empty-cell"><span style="color: #333; font-weight: 700;">{base}</span></div>'
            else:
                pct = data.get((i, j))
                
                if pct is None:
                    html += '<div class="pair-cell empty-cell"><span style="color: #999; font-size: 12px;">unch</span></div>'
                else:
                    color = get_color_from_pct(pct)
                    pair_name = f"{base}/{quote}"
                    
                    html += f'''
                    <div class="pair-cell" style="background-color: {color};">
                        <div class="pair-name">{pair_name}</div>
                        <div class="pair-value">{pct:+.2f}%</div>
                    </div>
                    '''
        
    html += '</div>'
    return html

# ------------------------------------------------------------
# 4. APPLICATION STREAMLIT
# ------------------------------------------------------------
st.markdown('<div class="main-title">Forex Market Map</div>', unsafe_allow_html=True)

today = datetime.now().strftime("%a, %b %dth, %Y")
st.markdown(f'<div class="date-info">{today}</div>', unsafe_allow_html=True)

# Sidebar avec paramètres
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
    # Vérifier la connexion OANDA
    if get_oanda_credentials()[0] is None:
        st.error("❌ Impossible de continuer sans credentials OANDA. Configurez-les dans les Secrets.")
    else:
        with st.spinner("📊 Chargement des données OANDA..."):
            # Récupération des données
            data = get_all_pairs_data(CURRENCIES, lookback_days=lookback)
            
            # Génération de la matrice
            matrix_html = generate_matrix_html(CURRENCIES, data)
            
            # Affichage
            st.components.v1.html(
                f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body {{
                            margin: 0;
                            padding: 20px;
                            background-color: #f8f9fa;
                            font-family: Arial, sans-serif;
                        }}
                        .matrix-grid {{
                            display: grid;
                            grid-template-columns: 80px repeat(8, 150px);
                            gap: 0;
                            margin: 0;
                            width: fit-content;
                        }}
                        .currency-header {{
                            background-color: #e8e8e8;
                            border: 1px solid #d0d0d0;
                            padding: 15px;
                            text-align: center;
                            font-weight: 700;
                            font-size: 14px;
                            color: #333;
                        }}
                        .pair-cell {{
                            border: 1px solid rgba(0,0,0,0.1);
                            padding: 10px;
                            text-align: center;
                            cursor: pointer;
                            transition: all 0.2s;
                            min-height: 60px;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                            align-items: center;
                        }}
                        .pair-cell:hover {{
                            transform: scale(1.05);
                            z-index: 10;
                            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                        }}
                        .pair-name {{
                            font-weight: 700;
                            font-size: 11px;
                            margin-bottom: 4px;
                            color: white;
                        }}
                        .pair-value {{
                            font-weight: 600;
                            font-size: 13px;
                            color: white;
                        }}
                        .empty-cell {{
                            background-color: #f0f0f0;
                            border: 1px solid #d0d0d0;
                        }}
                    </style>
                </head>
                <body>
                    {matrix_html}
                </body>
                </html>
                """,
                height=700,
                scrolling=True
            )
            
            st.success("✅ Matrice mise à jour avec succès !")
            
            # Légende
            st.markdown("---")
            st.markdown("""
            **Comment lire la matrice :**
            - 🟢 **Vert** : La devise de base (ligne) monte contre la devise de cotation (colonne)
            - 🔴 **Rouge** : La devise de base (ligne) baisse contre la devise de cotation (colonne)
            - Le pourcentage indique la variation sur la période choisie
            """)

else:
    st.info("👆 Cliquez pour charger la matrice des paires Forex (données OANDA)")
    
    # Exemple visuel de la matrice
    st.markdown("""
    ### 📊 À propos de cette matrice
    
    Cette application affiche une **matrice de corrélation des devises** en temps réel via l'API OANDA.
    
    Chaque cellule montre la performance d'une paire de devises :
    - **Ligne** : Devise de base
    - **Colonne** : Devise de cotation
    - **Couleur** : Force du mouvement (vert = hausse, rouge = baisse)
    
    **Exemple** : La cellule EUR/USD montre comment l'EUR performe contre l'USD.
    """)
