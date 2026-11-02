// netlify/functions/poster.js
// Proxy OMDb : la clé reste côté serveur (variable d'environnement OMDB_KEY).
exports.handler = async (event) => {
  const { i, t, s, y, type } = event.queryStringParameters || {};

  if (!process.env.OMDB_KEY) {
    return { statusCode: 500, body: JSON.stringify({ Response: 'False', Error: 'OMDB_KEY manquante' }) };
  }
  if (!i && !t && !s) {
    return { statusCode: 400, body: JSON.stringify({ Response: 'False', Error: 'Paramètre i, t ou s requis' }) };
  }

  const params = new URLSearchParams({ apikey: process.env.OMDB_KEY });
  if (i) params.set('i', i);
  else {
    params.set(t ? 't' : 's', t || s);
    if (y) params.set('y', y);
    if (type === 'movie' || type === 'series') params.set('type', type);
  }

  try {
    const res = await fetch(`https://www.omdbapi.com/?${params}`);
    const data = await res.json();
    // On ne met en cache (30 jours, CDN + navigateur) que les réponses réussies
    const cacheable = data.Response === 'True';
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': cacheable ? 'public, max-age=2592000' : 'no-store'
      },
      body: JSON.stringify(data)
    };
  } catch (e) {
    return { statusCode: 502, body: JSON.stringify({ Response: 'False', Error: 'OMDb injoignable' }) };
  }
};