import React, { useState, useEffect } from 'react';
import { ArrowUp, ArrowDown, Minus, RefreshCw } from 'lucide-react';

const CurrencyStrengthMeter = () => {
  const [strengths, setStrengths] = useState({});
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [loading, setLoading] = useState(false);

  // Les 8 devises majeures
  const currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD'];
  
  // Les 28 paires forex majeures (structure exacte)
  const forexPairs = [
    // USD pairs
    { pair: 'EUR/USD', base: 'EUR', quote: 'USD' },
    { pair: 'GBP/USD', base: 'GBP', quote: 'USD' },
    { pair: 'AUD/USD', base: 'AUD', quote: 'USD' },
    { pair: 'NZD/USD', base: 'NZD', quote: 'USD' },
    { pair: 'USD/JPY', base: 'USD', quote: 'JPY' },
    { pair: 'USD/CHF', base: 'USD', quote: 'CHF' },
    { pair: 'USD/CAD', base: 'USD', quote: 'CAD' },
    
    // EUR pairs (sans EUR/USD déjà listé)
    { pair: 'EUR/GBP', base: 'EUR', quote: 'GBP' },
    { pair: 'EUR/JPY', base: 'EUR', quote: 'JPY' },
    { pair: 'EUR/CHF', base: 'EUR', quote: 'CHF' },
    { pair: 'EUR/AUD', base: 'EUR', quote: 'AUD' },
    { pair: 'EUR/CAD', base: 'EUR', quote: 'CAD' },
    { pair: 'EUR/NZD', base: 'EUR', quote: 'NZD' },
    
    // GBP pairs
    { pair: 'GBP/JPY', base: 'GBP', quote: 'JPY' },
    { pair: 'GBP/CHF', base: 'GBP', quote: 'CHF' },
    { pair: 'GBP/AUD', base: 'GBP', quote: 'AUD' },
    { pair: 'GBP/CAD', base: 'GBP', quote: 'CAD' },
    { pair: 'GBP/NZD', base: 'GBP', quote: 'NZD' },
    
    // AUD pairs
    { pair: 'AUD/JPY', base: 'AUD', quote: 'JPY' },
    { pair: 'AUD/CHF', base: 'AUD', quote: 'CHF' },
    { pair: 'AUD/CAD', base: 'AUD', quote: 'CAD' },
    { pair: 'AUD/NZD', base: 'AUD', quote: 'NZD' },
    
    // NZD pairs
    { pair: 'NZD/JPY', base: 'NZD', quote: 'JPY' },
    { pair: 'NZD/CHF', base: 'NZD', quote: 'CHF' },
    { pair: 'NZD/CAD', base: 'NZD', quote: 'CAD' },
    
    // CAD pairs
    { pair: 'CAD/JPY', base: 'CAD', quote: 'JPY' },
    { pair: 'CAD/CHF', base: 'CAD', quote: 'CHF' },
    
    // CHF pairs
    { pair: 'CHF/JPY', base: 'CHF', quote: 'JPY' }
  ];

  // Actifs supplémentaires
  const additionalAssets = [
    { symbol: 'XAU/USD', name: 'Or', base: 2050, volatility: 50 },
    { symbol: 'XPT/USD', name: 'Platine', base: 950, volatility: 30 },
    { symbol: 'US30', name: 'Dow Jones', base: 37000, volatility: 500 },
    { symbol: 'NAS100', name: 'Nasdaq 100', base: 16000, volatility: 300 },
    { symbol: 'SPX500', name: 'S&P 500', base: 4700, volatility: 80 }
  ];

  // Générer des mouvements de prix simulés sur 24h
  const generatePriceMovements = () => {
    const movements = {};
    
    forexPairs.forEach(({ pair }) => {
      // Mouvement en pourcentage sur 24h (-5% à +5%)
      movements[pair] = (Math.random() - 0.5) * 10;
    });

    additionalAssets.forEach(({ symbol, base, volatility }) => {
      const change = (Math.random() - 0.5) * (volatility / base) * 100 * 2;
      movements[symbol] = change;
    });

    return movements;
  };

  // MÉTHODE RAW STRENGTH - Logique exacte des CSM professionnels
  const calculateRawStrength = () => {
    const movements = generatePriceMovements();
    const rawStrengths = {};

    // Initialiser à zéro
    currencies.forEach(curr => {
      rawStrengths[curr] = 0;
    });

    // Calculer la force brute pour chaque devise
    currencies.forEach(targetCurrency => {
      let totalStrength = 0;

      forexPairs.forEach(({ pair, base, quote }) => {
        const movement = movements[pair];

        if (base === targetCurrency) {
          // Si la devise est en BASE: mouvement positif = force
          totalStrength += movement;
        } else if (quote === targetCurrency) {
          // Si la devise est en QUOTE: mouvement négatif = force (donc on inverse)
          totalStrength -= movement;
        }
      });

      rawStrengths[targetCurrency] = totalStrength;
    });

    // Calculer les actifs supplémentaires (vs USD)
    additionalAssets.forEach(({ symbol }) => {
      rawStrengths[symbol] = movements[symbol];
    });

    // Vérification: la somme des 8 devises doit être ~0 (corrélation)
    const sum = currencies.reduce((acc, curr) => acc + rawStrengths[curr], 0);
    console.log('Vérification corrélation (doit être ~0):', sum.toFixed(2));

    // Déterminer les tendances
    const result = {};
    Object.keys(rawStrengths).forEach(key => {
      const strength = rawStrengths[key];
      result[key] = {
        rawScore: strength,
        trend: strength > 0.5 ? 'up' : strength < -0.5 ? 'down' : 'neutral',
        percentage: strength
      };
    });

    return result;
  };

  const refreshData = () => {
    setLoading(true);
    setTimeout(() => {
      setStrengths(calculateRawStrength());
      setLastUpdate(new Date());
      setLoading(false);
    }, 500);
  };

  useEffect(() => {
    refreshData();
    const interval = setInterval(refreshData, 60000);
    return () => clearInterval(interval);
  }, []);

  const getColorClass = (score) => {
    if (score > 5) return 'bg-green-600';
    if (score > 2) return 'bg-green-500';
    if (score > -2) return 'bg-yellow-500';
    if (score > -5) return 'bg-orange-500';
    return 'bg-red-600';
  };

  const getTrendIcon = (trend) => {
    if (trend === 'up') return <ArrowUp className="w-4 h-4" />;
    if (trend === 'down') return <ArrowDown className="w-4 h-4" />;
    return <Minus className="w-4 h-4" />;
  };

  // Trier par force décroissante
  const sortedCurrencies = currencies
    .map(curr => ({ curr, ...strengths[curr] }))
    .filter(item => item.rawScore !== undefined)
    .sort((a, b) => b.rawScore - a.rawScore);

  const sortedAssets = additionalAssets
    .map(({ symbol }) => ({ symbol, ...strengths[symbol] }))
    .filter(item => item.rawScore !== undefined)
    .sort((a, b) => b.rawScore - a.rawScore);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            Currency Strength Meter
          </h1>
          <p className="text-gray-400">Méthode Raw Strength - 28 Paires Forex + Actifs Majeurs</p>
          <p className="text-xs text-gray-500 mt-1">Algorithme professionnel: somme des mouvements sur 24h (non moyenné)</p>
        </div>

        {/* Controls */}
        <div className="flex justify-between items-center mb-6 bg-slate-800/50 backdrop-blur-sm rounded-lg p-4">
          <div className="text-sm text-gray-400">
            Dernière mise à jour: {lastUpdate.toLocaleTimeString('fr-FR')}
          </div>
          <button
            onClick={refreshData}
            disabled={loading}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-4 py-2 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Actualiser
          </button>
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Devises Majeures */}
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6">
            <h2 className="text-2xl font-bold mb-4 text-blue-400">
              Devises Majeures (Raw Strength)
            </h2>
            <div className="space-y-3">
              {sortedCurrencies.map(({ curr, rawScore, trend, percentage }) => (
                <div key={curr} className="bg-slate-700/50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl font-bold">{curr}</span>
                      {getTrendIcon(trend)}
                    </div>
                    <div className="text-right">
                      <div className={`text-lg font-bold ${percentage > 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {percentage > 0 ? '+' : ''}{percentage.toFixed(2)}%
                      </div>
                      <div className="text-sm text-gray-400">
                        Score brut: {rawScore.toFixed(2)}
                      </div>
                    </div>
                  </div>
                  <div className="relative w-full h-3 bg-slate-600 rounded-full overflow-hidden">
                    <div
                      className={`absolute left-1/2 h-full ${getColorClass(rawScore)} transition-all duration-500`}
                      style={{
                        width: `${Math.min(Math.abs(rawScore) * 3, 100)}%`,
                        transform: rawScore >= 0 ? 'translateX(0)' : 'translateX(-100%)'
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Vérification de corrélation */}
            <div className="mt-4 bg-blue-900/20 border border-blue-700/30 rounded-lg p-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="font-semibold">✓ Corrélation vérifiée:</span>
                <span className="text-gray-400">
                  La somme des 8 devises = {sortedCurrencies.reduce((acc, {rawScore}) => acc + rawScore, 0).toFixed(2)}
                  {' '}(≈0)
                </span>
              </div>
            </div>
          </div>

          {/* Actifs Supplémentaires */}
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6">
            <h2 className="text-2xl font-bold mb-4 text-purple-400">Métaux & Indices</h2>
            <div className="space-y-3">
              {sortedAssets.map(({ symbol, rawScore, trend, percentage }) => (
                <div key={symbol} className="bg-slate-700/50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold">{symbol}</span>
                      {getTrendIcon(trend)}
                    </div>
                    <div className="text-right">
                      <div className={`text-lg font-bold ${percentage > 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {percentage > 0 ? '+' : ''}{percentage.toFixed(2)}%
                      </div>
                      <div className="text-sm text-gray-400">
                        Score: {rawScore.toFixed(2)}
                      </div>
                    </div>
                  </div>
                  <div className="relative w-full h-3 bg-slate-600 rounded-full overflow-hidden">
                    <div
                      className={`absolute left-1/2 h-full ${getColorClass(rawScore)} transition-all duration-500`}
                      style={{
                        width: `${Math.min(Math.abs(rawScore) * 3, 100)}%`,
                        transform: rawScore >= 0 ? 'translateX(0)' : 'translateX(-100%)'
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Guide d'interprétation */}
            <div className="mt-6 bg-purple-900/30 border border-purple-700/50 rounded-lg p-4">
              <h3 className="font-bold mb-3 text-purple-300">📈 Méthode Raw Strength</h3>
              <ul className="text-sm text-gray-300 space-y-2">
                <li>• <strong>Score positif élevé</strong>: Forte demande (hausse générale)</li>
                <li>• <strong>Score négatif élevé</strong>: Forte vente (baisse générale)</li>
                <li>• <strong>Trading optimal</strong>: Combiner devise la + forte avec la + faible</li>
                <li>• <strong>Exemple</strong>: Si EUR = +15% et USD = -10%, alors EUR/USD devrait monter</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Tableau des 28 paires */}
        <div className="mt-6 bg-slate-800/50 backdrop-blur-sm rounded-xl p-6">
          <h2 className="text-xl font-bold mb-4 text-gray-300">
            Les 28 Paires Forex Analysées
          </h2>
          <div className="grid grid-cols-4 md:grid-cols-7 gap-2 text-xs">
            {forexPairs.map(({ pair }) => (
              <div key={pair} className="bg-slate-700/40 rounded px-2 py-1.5 text-center text-gray-300 hover:bg-slate-600/50 transition-colors">
                {pair}
              </div>
            ))}
          </div>
        </div>

        {/* Explication de l'algorithme */}
        <div className="mt-6 bg-gradient-to-r from-blue-900/40 to-purple-900/40 border border-blue-700/30 rounded-xl p-6">
          <h3 className="text-lg font-bold mb-3 text-blue-300">🔬 Logique de calcul (Raw Strength Method)</h3>
          <div className="grid md:grid-cols-2 gap-4 text-sm text-gray-300">
            <div>
              <p className="font-semibold mb-2">Pour chaque devise (ex: EUR):</p>
              <ol className="space-y-1 ml-4">
                <li>1. Identifier toutes les paires contenant EUR</li>
                <li>2. Calculer le % de mouvement sur 24h</li>
                <li>3. Si EUR en base: ajouter le %</li>
                <li>4. Si EUR en quote: soustraire le %</li>
                <li>5. Additionner (ne PAS moyenner)</li>
              </ol>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-4">
              <p className="font-semibold mb-2 text-yellow-300">Exemple AUD:</p>
              <div className="space-y-1 font-mono text-xs">
                <div>AUD/CAD = +2.2% → +2.2%</div>
                <div>AUD/USD = +1.6% → +1.6%</div>
                <div>EUR/AUD = -2.3% → <span className="text-green-400">+2.3%</span></div>
                <div>GBP/AUD = -1.9% → <span className="text-green-400">+1.9%</span></div>
                <div className="border-t border-gray-600 pt-1 mt-1 text-green-400 font-bold">
                  Total = +13.5% (Force brute)
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-sm text-gray-500">
          <p>Algorithme professionnel "Raw Strength" - Données simulées pour démonstration</p>
          <p className="mt-1">Mise à jour automatique toutes les 60 secondes</p>
        </div>
      </div>
    </div>
  );
};

export default CurrencyStrengthMeter;
