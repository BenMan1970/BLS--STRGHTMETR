# app.py — Strength Meter PRO (Version Modernisée)
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import zscore

# ----------------------------
# CONFIG - 28 Paires Forex + Métaux + Indices
# ----------------------------
CONFIG = {
    'tickers': {
        # 28 PAIRES FOREX MAJEURES
        'EURUSD=X': [20.0, 'EUR', 'USD', 'FX'],
        'GBPUSD=X': [18.0, 'GBP', 'USD', 'FX'],
        'USDJPY=X': [17.0, 'USD', 'JPY', 'FX'],
        'USDCHF=X': [15.0, 'USD', 'CHF', 'FX'],
        'AUDUSD=X': [14.0, 'AUD', 'USD', 'FX'],
        'USDCAD=X': [13.0, 'USD', 'CAD', 'FX'],
        'NZDUSD=X': [12.0, 'NZD', 'USD', 'FX'],
        
        'EURGBP=X': [11.0, 'EUR', 'GBP', 'FX'],
        'EURJPY=X': [10.0, 'EUR', 'JPY', 'FX'],
        'EURCHF=X': [9.0, 'EUR', 'CHF', 'FX'],
        'EURAUD=X': [8.0, 'EUR', 'AUD', 'FX'],
        'EURCAD=X': [7.0, 'EUR', 'CAD', 'FX'],
        'EURNZD=X': [6.0, 'EUR', 'NZD', 'FX'],
        
        'GBPJPY=X': [9.0, 'GBP', 'JPY', 'FX'],
        'GBPCHF=X': [8.0, 'GBP', 'CHF', 'FX'],
        'GBPAUD=X': [7.0, 'GBP', 'AUD', 'FX'],
        'GBPCAD=X': [6.0, 'GBP', 'CAD', 'FX'],
        'GBPNZD=X': [5.0, 'GBP', 'NZD', 'FX'],
        
        'AUDJPY=X': [7.0, 'AUD', 'JPY', 'FX'],
        'AUDCHF=X': [6.0, 'AUD', 'CHF', 'FX'],
        'AUDCAD=X': [5.0, 'AUD', 'CAD', 'FX'],
        'AUDNZD=X': [4.0, 'AUD', 'NZD', 'FX'],
        
        'NZDJPY=X': [5.0, 'NZD', 'JPY', 'FX'],
        'NZDCHF=X': [4.0, 'NZD', 'CHF', 'FX'],
        'NZDCAD=X': [3.0, 'NZD', 'CAD', 'FX'],
        
        'CADJPY=X': [5.0, 'CAD', 'JPY', 'FX'],
        'CADCHF=X': [4.0, 'CAD', 'CHF', 'FX'],
        
        'CHFJPY=X': [4.0, 'CHF', 'JPY', 'FX'],
        
        # MÉTAUX
        'GC=F': [15.0, 'XAU', 'USD', 'METAL'],
        'PL=F': [8.0, 'XPT', 'USD', 'METAL'],
        
        # INDICES
        '^DJI': [12.0, 'US30', 'USD', 'INDEX'],
        '^IXIC': [12.0, 'NAS100', 'USD', 'INDEX'],
        '^GSPC': [15.0, 'SPX500', 'USD', 'INDEX'],
    },
    'period': '60d',
    'interval': '1d',
    'lookback_days': 3,
    'atr_period': 14,
    'atr_floor_pct': 1e-4,
    'smoothing_span': 3,
    'category_mode': True
}

# ----------------------------
# UTIL: ATR
# ----------------------------
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

# ----------------------------
# Palette de couleurs moderne
# ----------------------------
def modern_color(score):
    """Retourne une couleur gradient moderne basée sur le score"""
    try:
        s = float(score)
    except Exception:
        s = 5.0
    
    if s <= 2:
        return '#ef4444'  # Rouge vif
    elif s <= 4:
        return '#f97316'  # Orange
    elif s <= 6:
        return '#eab308'  # Jaune/Ambre
    elif s <= 8:
        return '#22c55e'  # Vert
    else:
        return '#06b6d4'  # Cyan brillant

def get_category_icon(category):
    """Retourne une icône pour chaque catégorie"""
    icons = {
        'FX': '💱',
        'METAL': '🥇',
        'INDEX': '📈'
    }
    return icons.get(category, '📊')

# ----------------------------
# CORE: compute_strength
# ----------------------------
def compute_strength(config=CONFIG):
    tickers_cfg = config['tickers']
    lookback = config['lookback_days']
    atr_period = config['atr_period']
    atr_floor_pct = config['atr_floor_pct']

    all_tickers = list(tickers_cfg.keys())

    try:
        data = yf.download(all_tickers, period=config['period'], interval=config['interval'],
                           group_by='ticker', progress=False, threads=True)
    except Exception as e:
        st.error(f"❌ Erreur téléchargement yfinance: {e}")
        return pd.DataFrame(), {}

    entities = set()
    for t, v in tickers_cfg.items():
        entities.add(v[1])
        entities.add(v[2])

    scores_acc = {e: {'weighted_sum': 0.0, 'total_weight': 0.0} for e in entities}
    categories = {}
    if config['category_mode']:
        for t, v in tickers_cfg.items():
            cat = v[3]
            if cat not in categories:
                categories[cat] = {e: {'weighted_sum': 0.0, 'total_weight': 0.0} for e in entities}

    for ticker, info in tickers_cfg.items():
        weight, base, quote, category = info

        try:
            if ticker not in data.columns.get_level_values(0):
                continue
            df = data[ticker].dropna()
        except Exception:
            try:
                df = data.dropna()
            except Exception:
                continue

        if df.empty or len(df) < max(atr_period + 2, lookback + 2):
            continue

        close = df['Close']
        price_now = close.iloc[-1]
        price_past = close.shift(lookback).iloc[-1]
        if pd.isna(price_now) or pd.isna(price_past) or price_past == 0:
            continue

        raw_move_pct = (price_now - price_past) / price_past

        atr = calculate_atr(df, period=atr_period)
        current_atr = atr.iloc[-1]
        atr_pct = current_atr / price_now if price_now != 0 else atr_floor_pct
        if pd.isna(atr_pct) or atr_pct <= 0:
            atr_pct = atr_floor_pct
        atr_pct = max(atr_pct, atr_floor_pct)

        strength = raw_move_pct / atr_pct

        scores_acc[base]['weighted_sum'] += strength * weight
        scores_acc[base]['total_weight'] += weight
        scores_acc[quote]['weighted_sum'] += (-strength) * weight
        scores_acc[quote]['total_weight'] += weight

        if config['category_mode']:
            categories[category][base]['weighted_sum'] += strength * weight
            categories[category][base]['total_weight'] += weight
            categories[category][quote]['weighted_sum'] += (-strength) * weight
            categories[category][quote]['total_weight'] += weight

    raw_values = {}
    for ent, v in scores_acc.items():
        raw_values[ent] = v['weighted_sum'] / v['total_weight'] if v['total_weight'] > 0 else 0.0

    df_raw = pd.Series(raw_values, name='raw_strength').to_frame()

    vals = df_raw['raw_strength'].values
    if np.nanstd(vals) == 0:
        z = np.zeros_like(vals)
    else:
        z = zscore(vals, nan_policy='omit')
    z = np.nan_to_num(z)
    z = np.clip(z, -3, 3)
    scaled = 5 + (z / 6) * 10
    scaled = np.clip(scaled, 0, 10)

    df_raw['score'] = np.round(scaled, 2)

    if config['smoothing_span'] > 1:
        df_raw['score_smoothed'] = df_raw['score'].ewm(span=config['smoothing_span'], adjust=False).mean()
    else:
        df_raw['score_smoothed'] = df_raw['score']

    df_raw = df_raw.sort_values(by='score_smoothed', ascending=False)

    category_frames = {}
    if config['category_mode']:
        for cat, acc in categories.items():
            tmp = {}
            for ent, v in acc.items():
                tmp[ent] = v['weighted_sum'] / v['total_weight'] if v['total_weight'] > 0 else 0.0
            s = pd.Series(tmp)
            if s.std() == 0:
                zc = np.zeros_like(s.values)
            else:
                zc = zscore(s.values, nan_policy='omit')
            zc = np.clip(np.nan_to_num(zc), -3, 3)
            scaled_c = 5 + (zc / 6) * 10
            scaled_c = np.clip(scaled_c, 0, 10)
            category_frames[cat] = pd.DataFrame({'score': np.round(scaled_c, 2)}, index=s.index).sort_values(by='score', ascending=False)

    return df_raw, category_frames

# ----------------------------
# STREAMLIT UI - Design Moderne
# ----------------------------
st.set_page_config(
    page_title="Strength Meter PRO",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS Moderne et Élégant
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    /* Background global */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%);
        font-family: 'Inter', sans-serif;
    }
    
    /* Header personnalisé */
    .main-header {
        text-align: center;
        padding: 2rem 0 1rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 700;
        letter-spacing: -1px;
    }
    
    .subtitle {
        text-align: center;
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Container des barres */
    .bar-container {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        margin: 1.5rem 0;
    }
    
    /* Item de barre individuel */
    .bar-item {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1rem 1.25rem;
        background: rgba(30, 41, 59, 0.5);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.1);
        transition: all 0.3s ease;
    }
    
    .bar-item:hover {
        background: rgba(30, 41, 59, 0.7);
        border-color: rgba(148, 163, 184, 0.3);
        transform: translateX(5px);
    }
    
    /* Label de la paire */
    .bar-label {
        min-width: 120px;
        font-weight: 600;
        font-size: 0.95rem;
        color: #e2e8f0;
        letter-spacing: 0.5px;
    }
    
    /* Barre de progression */
    .progress-bar {
        flex: 1;
        height: 24px;
        background: rgba(15, 23, 42, 0.8);
        border-radius: 12px;
        overflow: hidden;
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
    }
    
    .progress-fill {
        height: 100%;
        border-radius: 12px;
        transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    
    .progress-fill::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(
            90deg,
            transparent,
            rgba(255, 255, 255, 0.2),
            transparent
        );
        animation: shimmer 2s infinite;
    }
    
    @keyframes shimmer {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }
    
    /* Score */
    .score-badge {
        min-width: 70px;
        text-align: center;
        padding: 0.4rem 0.8rem;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.95rem;
        background: rgba(51, 65, 85, 0.5);
        color: #f1f5f9;
    }
    
    /* Section headers */
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 2rem 0 1rem 0;
        padding: 0.75rem 1rem;
        background: rgba(51, 65, 85, 0.3);
        border-radius: 10px;
        border-left: 4px solid #667eea;
    }
    
    .section-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: #f1f5f9;
        margin: 0;
    }
    
    .section-icon {
        font-size: 1.5rem;
    }
    
    /* Bouton personnalisé */
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 600;
        font-size: 1.1rem;
        padding: 0.8rem 2rem;
        border: none;
        border-radius: 12px;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
    }
    
    /* Info box */
    .info-box {
        background: rgba(59, 130, 246, 0.1);
        border-left: 4px solid #3b82f6;
        padding: 1rem 1.25rem;
        border-radius: 8px;
        color: #bfdbfe;
        margin: 1rem 0;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .main-header { font-size: 2rem; }
        .bar-label { min-width: 90px; font-size: 0.85rem; }
        .score-badge { min-width: 60px; font-size: 0.85rem; }
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<h1 class="main-header">📊 Strength Meter PRO</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Analyseur de force des devises, métaux et indices en temps réel</p>', unsafe_allow_html=True)

# Informations
st.markdown("""
<div class="info-box">
    <strong>🎯 Méthodologie :</strong> Calcul basé sur ATR normalisé + Z-score | 
    <strong>📅 Période :</strong> 60 jours | 
    <strong>🔄 Lookback :</strong> 3 jours | 
    <strong>📊 Assets :</strong> 28 paires FX + 2 métaux + 3 indices
</div>
""", unsafe_allow_html=True)

# Bouton de calcul
if st.button("🚀 LANCER L'ANALYSE", use_container_width=True):
    with st.spinner("⏳ Téléchargement des données et calcul en cours..."):
        df_entities, cats = compute_strength(CONFIG)

    if df_entities is None or df_entities.empty:
        st.error("❌ Aucune donnée calculée. Vérifiez votre connexion ou la configuration des tickers.")
    else:
        # SECTION 1: ENTITÉS
        st.markdown("""
        <div class="section-header">
            <span class="section-icon">🌍</span>
            <h2 class="section-title">Force des Devises & Assets</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div class='bar-container'>", unsafe_allow_html=True)
        for ent in df_entities.index:
            score = float(df_entities.loc[ent, 'score_smoothed'])
            pct = max(min(score / 10.0, 1.0), 0.0) * 100
            color = modern_color(score)
            
            bar_html = f"""
            <div class='bar-item'>
                <div class='bar-label'>{ent}</div>
                <div class='progress-bar'>
                    <div class='progress-fill' style='width:{pct}%; background: linear-gradient(90deg, {color}, {color}dd);'></div>
                </div>
                <div class='score-badge' style='background: {color}22; color: {color};'>{score:.2f}</div>
            </div>
            """
            st.markdown(bar_html, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # SECTION 2: PAIRES
        st.markdown("""
        <div class="section-header">
            <span class="section-icon">💹</span>
            <h2 class="section-title">Analyse par Paire</h2>
        </div>
        """, unsafe_allow_html=True)

        pairs_list = []
        for ticker, info in CONFIG['tickers'].items():
            weight, base, quote, category = info
            if base in df_entities.index and quote in df_entities.index:
                base_s = float(df_entities.loc[base, 'score_smoothed'])
                quote_s = float(df_entities.loc[quote, 'score_smoothed'])
                diff = base_s - quote_s
                pair_score = (diff + 10.0) / 20.0 * 10.0
                pair_score = float(np.clip(pair_score, 0.0, 10.0))
            else:
                pair_score = 5.0
            pairs_list.append({
                'ticker': ticker,
                'base': base,
                'quote': quote,
                'score': round(pair_score, 2),
                'category': category
            })

        df_pairs = pd.DataFrame(pairs_list).sort_values(by='score', ascending=False).reset_index(drop=True)

        st.markdown("<div class='bar-container'>", unsafe_allow_html=True)
        for _, row in df_pairs.iterrows():
            ticker = row['ticker']
            score = float(row['score'])
            category = row['category']
            icon = get_category_icon(category)
            pct = max(min(score / 10.0, 1.0), 0.0) * 100
            color = modern_color(score)
            
            html = f"""
            <div class='bar-item'>
                <div class='bar-label'>{icon} {ticker}</div>
                <div class='progress-bar'>
                    <div class='progress-fill' style='width:{pct}%; background: linear-gradient(90deg, {color}, {color}dd);'></div>
                </div>
                <div class='score-badge' style='background: {color}22; color: {color};'>{score:.2f}</div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Téléchargement CSV
        st.markdown("---")
        out_entities = df_entities.reset_index().rename(columns={'index': 'entity'})
        out_pairs = df_pairs.copy()
        csv_buf = "== ENTITÉS ==\n" + out_entities.to_csv(index=False) + "\n\n== PAIRES ==\n" + out_pairs.to_csv(index=False)
        st.download_button(
            "📥 Télécharger les résultats (CSV)",
            csv_buf.encode('utf-8'),
            file_name='strength_analysis.csv',
            mime='text/csv',
            use_container_width=True
        )

        # Affichage par catégorie (optionnel)
        if cats:
            st.markdown("""
            <div class="section-header">
                <span class="section-icon">📂</span>
                <h2 class="section-title">Vue par Catégorie</h2>
            </div>
            """, unsafe_allow_html=True)
            
            cols = st.columns(len(cats))
            for idx, (cat_name, frame) in enumerate(cats.items()):
                with cols[idx]:
                    st.markdown(f"**{get_category_icon(cat_name)} {cat_name}**")
                    
                    # Fonction pour colorer les cellules
                    def color_score(val):
                        try:
                            score = float(val)
                            color = modern_color(score)
                            return f'background-color: {color}22; color: {color}; font-weight: 600;'
                        except:
                            return ''
                    
                    st.dataframe(
                        frame.style.applymap(color_score, subset=['score']),
                        height=300,
                        use_container_width=True
                    )

else:
    st.markdown("""
    <div class="info-box">
        👆 Cliquez sur le bouton ci-dessus pour lancer l'analyse complète des 33 instruments financiers.
    </div>
    """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
<p style='text-align: center; color: #64748b; font-size: 0.9rem;'>
    Made with 💜 | Données: Yahoo Finance | Mise à jour en temps réel
</p>
""", unsafe_allow_html=True)
