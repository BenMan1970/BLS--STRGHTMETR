import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore

# ------------------------------------------------------------
# 1. STYLE CSS
# ------------------------------------------------------------
st.set_page_config(page_title="Forex Currency Matrix", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    
    .matrix-container {
        display: inline-block;
        margin: 20px 0;
    }
    
    .matrix-table {
        border-collapse: collapse;
        font-family: Arial, sans-serif;
    }
    
    .matrix-cell {
        width: 100px;
        height: 50px;
        text-align: center;
        vertical-align: middle;
        border: 1px solid rgba(255,255,255,0.1);
        transition: transform 0.2s;
    }
    
    .matrix-cell:hover {
        transform: scale(1.05);
        border-color: rgba(255,255,255,0.5);
        cursor: pointer;
        z-index: 10;
        position: relative;
    }
    
    .cell-pair {
        font-weight: 700;
        font-size: 11px;
        display: block;
        margin-bottom: 3px;
    }
    
    .cell-value {
        font-weight: 600;
        font-size: 13px;
        font-family: 'Courier New', monospace;
    }
    
    .header-cell {
        background-color: #1a1a1a;
        color: #8b949e;
        font-weight: 700;
        font-size: 14px;
        width: 100px;
        height: 50px;
        text-align: center;
        vertical-align: middle;
        border: 1px solid rgba(255,255,255,0.1);
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 2. CONFIGURATION
# ------------------------------------------------------------
CONFIG = {
    'period': '60d',
    'interval': '1d',
    'lookback_days': 3,
    'atr_period': 14
}

# Devises principales pour la matrice
CURRENCIES = ['EUR', 'USD', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']

# ------------------------------------------------------------
# 3. MOTEUR DE CALCUL
# ------------------------------------------------------------
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

def get_pair_ticker(base, quote):
    """Convertit une paire de devises en ticker Yahoo Finance"""
    pair = f"{base}{quote}"
    # Mappings spéciaux
    if pair in ['EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD']:
        return f"{pair}=X"
    elif pair in ['USDJPY', 'USDCHF', 'USDCAD']:
        return f"{pair}=X"
    else:
        return f"{pair}=X"

def calculate_pair_strength(base, quote, config):
    """Calcule la force relative d'une paire"""
    ticker = get_pair_ticker(base, quote)
    
    try:
        df = yf.download(ticker, period=config['period'], interval=config['interval'], progress=False)
        if df.empty or len(df) < 20:
            return None
            
        close = df['Close']
        price_now = close.iloc[-1]
        price_past = close.shift(config['lookback_days']).iloc[-1]
        
        if pd.isna(price_now) or pd.isna(price_past) or price_past == 0:
            return None

        # Calcul de la force
        raw_move_pct = (price_now - price_past) / price_past
        atr = calculate_atr(df, config['atr_period']).iloc[-1]
        atr_pct = (atr / price_now) if price_now != 0 else 0.001
        strength = raw_move_pct / max(atr_pct, 0.0001)
        
        return {
            'raw_score': strength,
            'pct_change': raw_move_pct * 100
        }
    except:
        return None

def get_all_pairs_data(currencies, config):
    """Récupère toutes les données des paires"""
    results = {}
    
    with st.spinner("Téléchargement des données..."):
        progress_bar = st.progress(0)
        total = len(currencies) * len(currencies)
        current = 0
        
        for base in currencies:
            for quote in currencies:
                if base == quote:
                    results[(base, quote)] = None
                else:
                    data = calculate_pair_strength(base, quote, config)
                    results[(base, quote)] = data
                
                current += 1
                progress_bar.progress(current / total)
        
        progress_bar.empty()
    
    return results

def normalize_scores(results):
    """Normalise les scores sur 0-10"""
    valid_scores = [v['raw_score'] for v in results.values() if v is not None]
    
    if not valid_scores:
        return results
    
    z = zscore(valid_scores)
    z = np.clip(np.nan_to_num(z), -2.5, 2.5)
    normalized = 5 + (z / 5) * 10
    normalized = np.clip(normalized, 0, 10)
    
    idx = 0
    for key in results:
        if results[key] is not None:
            results[key]['score'] = normalized[idx]
            idx += 1
    
    return results

# ------------------------------------------------------------
# 4. GÉNÉRATEUR DE MATRICE HTML
# ------------------------------------------------------------
def get_color(score):
    """Palette de couleurs basée sur le score"""
    if score is None:
        return "#1a1a1a"
    
    if score >= 8.5: return "#064e3b"  # Vert Foncé
    if score >= 7.0: return "#15803d"  # Vert
    if score >= 6.0: return "#22c55e"  # Vert Clair
    if score >= 5.5: return "#4b5563"  # Gris-Vert
    
    if score <= 1.5: return "#7f1d1d"  # Rouge Foncé
    if score <= 3.0: return "#b91c1c"  # Rouge
    if score <= 4.0: return "#ef4444"  # Rouge Clair
    if score <= 4.5: return "#4b5563"  # Gris-Rouge
    
    return "#374151"  # Gris Neutre

def generate_currency_matrix(currencies, data):
    """Génère la matrice HTML des devises"""
    html = '<div class="matrix-container"><table class="matrix-table">'
    
    # Ligne d'en-tête
    html += '<tr><td class="header-cell"></td>'
    for quote in currencies:
        html += f'<td class="header-cell">{quote}</td>'
    html += '</tr>'
    
    # Lignes de données
    for base in currencies:
        html += f'<tr><td class="header-cell">{base}</td>'
        
        for quote in currencies:
            if base == quote:
                # Cellule diagonale
                html += f'<td class="matrix-cell header-cell">{base}</td>'
            else:
                pair_data = data.get((base, quote))
                
                if pair_data is None:
                    html += '<td class="matrix-cell" style="background-color: #1a1a1a; color: #666;">-</td>'
                else:
                    score = pair_data.get('score', 5)
                    pct = pair_data.get('pct_change', 0)
                    color = get_color(score)
                    
                    html += f'''
                    <td class="matrix-cell" style="background-color: {color}; color: white;">
                        <span class="cell-pair">{base}/{quote}</span>
                        <span class="cell-value">{pct:+.2f}%</span>
                    </td>
                    '''
        
        html += '</tr>'
    
    html += '</table></div>'
    return html

# ------------------------------------------------------------
# 5. APPLICATION STREAMLIT
# ------------------------------------------------------------
st.title("💱 Forex Currency Strength Matrix")
st.write("Matrice de force des devises. Vert = Force relative | Rouge = Faiblesse relative")

col1, col2 = st.columns([1, 3])

with col1:
    st.markdown("### Paramètres")
    lookback = st.slider("Période d'analyse (jours)", 1, 10, CONFIG['lookback_days'])
    CONFIG['lookback_days'] = lookback

if st.button("🚀 ANALYSER LE MARCHÉ", type="primary"):
    # Récupération des données
    data = get_all_pairs_data(CURRENCIES, CONFIG)
    
    # Normalisation
    data = normalize_scores(data)
    
    # Génération et affichage
    matrix_html = generate_currency_matrix(CURRENCIES, data)
    
    st.components.v1.html(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    background-color: transparent;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                }}
                .matrix-container {{
                    display: inline-block;
                    margin: 0 auto;
                }}
                .matrix-table {{
                    border-collapse: collapse;
                    font-family: Arial, sans-serif;
                }}
                .matrix-cell {{
                    width: 100px;
                    height: 50px;
                    text-align: center;
                    vertical-align: middle;
                    border: 1px solid rgba(255,255,255,0.1);
                    transition: transform 0.2s;
                }}
                .matrix-cell:hover {{
                    transform: scale(1.05);
                    border-color: rgba(255,255,255,0.5);
                    cursor: pointer;
                    z-index: 10;
                    position: relative;
                }}
                .cell-pair {{
                    font-weight: 700;
                    font-size: 11px;
                    display: block;
                    margin-bottom: 3px;
                }}
                .cell-value {{
                    font-weight: 600;
                    font-size: 13px;
                    font-family: 'Courier New', monospace;
                }}
                .header-cell {{
                    background-color: #1a1a1a;
                    color: #8b949e;
                    font-weight: 700;
                    font-size: 14px;
                    width: 100px;
                    height: 50px;
                    text-align: center;
                    vertical-align: middle;
                    border: 1px solid rgba(255,255,255,0.1);
                }}
            </style>
        </head>
        <body>
            {matrix_html}
        </body>
        </html>
        """,
        height=550,
        scrolling=False
    )
    
    # Légende
    st.markdown("---")
    st.markdown("""
    **Comment lire la matrice :**
    - 🟢 **Vert** : La devise de base (ligne) est forte par rapport à la devise de cotation (colonne)
    - 🔴 **Rouge** : La devise de base (ligne) est faible par rapport à la devise de cotation (colonne)
    - Le pourcentage indique la variation sur la période choisie
    """)

else:
    st.info("👆 Cliquez sur le bouton pour générer la matrice des forces des devises")
    
    # Exemple visuel
    st.markdown("### Exemple de matrice")
    st.image("https://via.placeholder.com/800x400/0e1117/8b949e?text=Matrice+des+devises", 
             caption="La matrice affichera toutes les paires croisées avec vos couleurs")
