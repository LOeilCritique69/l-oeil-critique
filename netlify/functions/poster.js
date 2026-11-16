// netlify/functions/poster.js
const CORS_HEADERS = {
  'Content-Type': 'application/json',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type'
};

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: CORS_HEADERS, body: '' };
  }

  const { i, t, s, y, type } = event.queryStringParameters || {};

  if (!process.env.OMDB_KEY) {
    return {
      statusCode: 500,
      headers: CORS_HEADERS,
      body: JSON.stringify({ Response: 'False', Error: 'OMDB_KEY manquante' })
    };
  }
  if (!i && !t && !s) {
    return {
      statusCode: 400,
      headers: CORS_HEADERS,
      body: JSON.stringify({ Response: 'False', Error: 'Paramètre i, t ou s requis' })
    };
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
    const cacheable = data.Response === 'True';
    return {
      statusCode: 200,
      headers: {
        ...CORS_HEADERS,
        'Cache-Control': cacheable ? 'public, max-age=2592000' : 'no-store'
      },
      body: JSON.stringify(data)
    };
  } catch (e) {
    return {
      statusCode: 502,
      headers: CORS_HEADERS,
      body: JSON.stringify({ Response: 'False', Error: 'OMDb injoignable' })
    };
  }
};