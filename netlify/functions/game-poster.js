exports.handler = async function (event) {
  const title = (event.queryStringParameters && event.queryStringParameters.title) || "";
  if (!title.trim()) {
    return { statusCode: 400, body: JSON.stringify({ url: "" }) };
  }

  const API_KEY = process.env.STEAMGRIDDB_API_KEY || "7fa6fbc92089665376b8f9e79c219d15";
  const headers = {
    Authorization: "Bearer " + API_KEY,
    "User-Agent": "LOeilCritique/1.0",
  };

  try {
    // 1. Recherche du jeu sur SteamGridDB
    const searchRes = await fetch(
      "https://www.steamgriddb.com/api/v2/search/autocomplete/" + encodeURIComponent(title),
      { headers }
    );
    const searchData = await searchRes.json();
    const first = searchData && searchData.success && searchData.data && searchData.data[0];

    if (first && first.id) {
      const gridsRes = await fetch(
        "https://www.steamgriddb.com/api/v2/grids/game/" + first.id + "?dimensions=600x900&types=static",
        { headers }
      );
      const gridsData = await gridsRes.json();
      const gridItem = gridsData && gridsData.success && gridsData.data && gridsData.data[0];
      if (gridItem && gridItem.url) {
        return {
          statusCode: 200,
          headers: {
            "Content-Type": "application/json",
            "Cache-Control": "public, max-age=86400",
          },
          body: JSON.stringify({ url: gridItem.url }),
        };
      }
    }

    // 2. Fallback sur Steam Store
    const steamRes = await fetch(
      "https://store.steampowered.com/api/storesearch/?term=" + encodeURIComponent(title) + "&l=french&cc=FR"
    );
    const steamData = await steamRes.json();
    const steamHit = steamData && steamData.items && steamData.items[0];
    if (steamHit && steamHit.id) {
      return {
        statusCode: 200,
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "public, max-age=86400",
        },
        body: JSON.stringify({
          url: "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/" + steamHit.id + "/library_600x900.jpg",
        }),
      };
    }

    return {
      statusCode: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: "" }),
    };
  } catch (err) {
    return {
      statusCode: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: "" }),
    };
  }
};