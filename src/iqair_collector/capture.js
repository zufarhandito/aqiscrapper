() => {
  // Only read the public station route; never serialize root/customer/session data.
  const prefix = 'window.__reactRouterContext.streamController.enqueue("[{';
  const script = [...document.scripts].find(x => x.textContent.startsWith(prefix));
  if (!script) throw new Error('PUBLIC_STATE_MISSING');
  const text = script.textContent;
  const table = JSON.parse(JSON.parse(text.slice(text.indexOf('(') + 1, text.lastIndexOf(')'))));
  if (!Array.isArray(table) || table.length > 100000) throw new Error('STATE_FORMAT_CHANGED');
  const seen = new Map();
  function decode(i, depth = 0) {
    if (!Number.isInteger(i) || i >= table.length || depth > 100) throw new Error('STATE_REFERENCE_INVALID');
    if (i < 0) return null;
    if (seen.has(i)) return seen.get(i);
    const v = table[i];
    if (Array.isArray(v)) {
      const out = []; seen.set(i, out);
      for (const n of v) out.push(typeof n === 'number' ? decode(n, depth + 1) : n);
      return out;
    }
    if (v && typeof v === 'object') {
      const out = Object.create(null); seen.set(i, out);
      for (const [k, n] of Object.entries(v)) {
        const key = k.startsWith('_') ? decode(Number(k.slice(1)), depth + 1) : k;
        out[key] = typeof n === 'number' ? decode(n, depth + 1) : n;
      }
      return out;
    }
    return v;
  }
  // Resolve only route data, without materializing unrelated customer fields.
  const root = table[0];
  const loaderKey = Object.keys(root).find(k => table[Number(k.slice(1))] === 'loaderData');
  const routes = table[root[loaderKey]];
  const routeKey = Object.keys(routes).find(k => table[Number(k.slice(1))] === 'routes/$(locale).air-quality.$');
  if (!routeKey) throw new Error('STATION_ROUTE_MISSING');
  const route = decode(routes[routeKey]);
  const d = route.details;
  return {
    captured_at_utc: new Date().toISOString(), source_url: location.href, type: route.type,
    details: {id: d.id, name: d.name, type: d.type, timezone: d.timezone,
      coordinates: d.coordinates, contributors: d.contributors, current: d.current},
    ui: {heading: document.querySelector('h1')?.outerHTML,
      label: document.querySelector('h2')?.outerHTML}
  };
}
