import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore

# ------------------------------------------------------------
# CONFIGURATION
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
        margin-bottom: 10px;
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
        font-size: 12px;
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

CONFIG = {
    'period': '60d',
    'interval': '1d',
    'lookback_days': 1,
    'atr_period': 14
}

# Ordre exact de l'image
CURRENCIES = ['EUR', 'USD', 'CAD', 'CHF', 'NZD', 'AUD', 'JPY', 'GBP']

# ------------------------------------------------------------
# MOTEUR DE CALCUL
# ------------------------------------------------------------
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

def get_pair_ticker(base, quote):
    """Convertit une paire en ticker Yahoo Finance"""
    pair = f"{base}{quote}"
    return f"{pair}=X"

def calculate_pair_strength(base, quote, config):
    """Calcule la variation % d'une paire"""
    ticker = get_pair_ticker(base, quote)
    
    try:
        df = yf.download(ticker, period=config['period'], interval=config['interval'], progress=False)
        if df.empty or len(df) < 20:
            # Essayer l'inverse
            ticker_inv = get_pair_ticker(quote, base)
            df = yf.download(ticker_inv, period=config['period'], interval=config['interval'], progress=False)
            if df.empty or len(df) < 20:
                return None
            inverse = True
        else:
            inverse = False
            
        close = df['Close']
        price_now = close.iloc[-1]
        price_past = close.iloc[-2]  # Jour précédent
        
        if pd.isna(price_now) or pd.isna(price_past) or price_past == 0:
            return None

        # Calcul variation %
        pct_change = ((price_now - price_past) / price_past) * 100
        
        if inverse:
            pct_change = -pct_change
        
        return pct_change
    except:
        return None

def get_all_pairs_data(currencies, config):
    """Récupère toutes les variations"""
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
                status.text(f"Analyse {base}/{quote}...")
                pct = calculate_pair_strength(base, quote, config)
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
    if pct >= 0.20: return "#006400"    # Vert très foncé
    if pct >= 0.15: return "#228B22"    # Vert foncé
    if pct >= 0.10: return "#32CD32"    # Vert
    if pct >= 0.05: return "#90EE90"    # Vert clair
    if pct >= 0.01: return "#98FB98"    # Vert très clair
    
    # Rouge (négatif)
    if pct <= -0.20: return "#8B0000"   # Rouge très foncé
    if pct <= -0.15: return "#B22222"   # Rouge foncé
    if pct <= -0.10: return "#DC143C"   # Rouge
    if pct <= -0.05: return "#FF6347"   # Rouge clair
    if pct <= -0.01: return "#FFA07A"   # Rouge très clair
    
    return "#D3D3D3"  # Gris neutre

# ------------------------------------------------------------
# GÉNÉRATEUR HTML
# ------------------------------------------------------------
def generate_matrix_html(currencies, data):
    """Génère la matrice exactement comme l'image"""
    html = '<div class="matrix-grid">'
    
    # Première ligne : en-têtes des colonnes (devises quote)
    html += '<div class="currency-header"></div>'  # Coin vide
    for currency in currencies:
        html += f'<div class="currency-header">{currency}</div>'
    
    # Lignes de données
    for i, base in enumerate(currencies):
        # En-tête de ligne (devise base)
        html += f'<div class="currency-header">{base}</div>'
        
        # Cellules de paires
        for j, quote in enumerate(currencies):
            if i == j:
                # Cellule diagonale (devise contre elle-même)
                html += f'<div class="pair-cell empty-cell"><span style="color: #333; font-weight: 700;">{base}</span></div>'
            else:
                pct = data.get((i, j))
                
                if pct is None:
                    html += '<div class="pair-cell empty-cell"><span style="color: #999;">unch</span></div>'
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
# APPLICATION
# ------------------------------------------------------------
st.markdown('<div class="main-title">Forex Market Map</div>', unsafe_allow_html=True)

from datetime import datetime
today = datetime.now().strftime("%a, %b %dth, %Y")
st.markdown(f'<div class="date-info">{today}</div>', unsafe_allow_html=True)

if st.button("🔄 Actualiser les données", type="primary"):
    with st.spinner("Chargement des données du marché..."):
        # Récupération des données
        data = get_all_pairs_data(CURRENCIES, CONFIG)
        
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
                        font-size: 12px;
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

else:
    st.info("👆 Cliquez pour charger la matrice du marché Forex")
             
