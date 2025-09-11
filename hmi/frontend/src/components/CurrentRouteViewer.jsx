export default function CurrentRouteViewer({
  sensors = {},
  routes = {},
  currentRoute,
  selectedRoute = '',
  setSelectedRoute = () => {},
  startRoute = () => {},
  cancelRoute = () => {},
  currentWpIdx = 0,
  mode = 'Manual',
}) {
  const selected = selectedRoute || '';

  const routeNames = Object.keys(routes);
  const waypoints = selected ? routes[selected] || [] : [];

  const isActive = (mode || '').startsWith('Route') && currentRoute === selected;

  const normalizeLng = (lng) => {
    if (!Number.isFinite(lng)) return lng;
    return ((lng + 180) % 360 + 360) % 360 - 180;
  };
  const normalizeLat = (lat) => {
    if (!Number.isFinite(lat)) return lat;
    return Math.max(-90, Math.min(90, lat));
  };

  const toDMS = (deg) => {
    const absolute = Math.abs(deg);
    const d = Math.floor(absolute);
    const mFloat = (absolute - d) * 60;
    const m = Math.floor(mFloat);
    const s = ((mFloat - m) * 60).toFixed(2);
    const sign = deg < 0 ? '-' : '';
    return `${sign}${d}° ${m}' ${s}"`;
  };

  const fmtLatLon = (v) => {
    if (v === undefined || v === null) return 'Unavaliable';
    return toDMS(Number(v));
  };

  const haversine = (lat1, lon1, lat2, lon2) => {
    const R = 6371000;
    const toRad = (deg) => (deg * Math.PI) / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  };

  const target = waypoints[currentWpIdx];
  const latRaw =
    sensors.gps_latitude ?? sensors.latitude ?? sensors.lat ?? sensors.y ?? null;
  const lonRaw =
    sensors.gps_longitude ??
    sensors.longitude ??
    sensors.lon ??
    sensors.lng ??
    sensors.long ??
    null;
  const lat = latRaw == null ? NaN : Number(latRaw);
  const lon = lonRaw == null ? NaN : Number(lonRaw);
  const remaining =
    target && Number.isFinite(lat) && Number.isFinite(lon)
      ? haversine(
          normalizeLat(lat),
          normalizeLng(lon),
          normalizeLat(Number(target.lat)),
          normalizeLng(Number(target.lon))
        )
      : null;

  const handleAction = () => {
    if (isActive) cancelRoute();
    else if (selected) startRoute(selected);
  };

  return (
    <div className="current-route">
      <div className="controls">
        <select value={selected} onChange={(e) => setSelectedRoute(e.target.value)}>
          <option value="">Select route</option>
          {routeNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <button onClick={handleAction} disabled={!selected && !isActive}>
          {isActive ? 'Abort Route' : 'Start Route'}
        </button>
      </div>

      <table className="route-table">
        <thead>
          <tr>
            <th>#</th>
            <th>✓</th>
            <th>Lat</th>
            <th>Lon</th>
          </tr>
        </thead>
        <tbody>
          {waypoints.map((wp, idx) => (
            <tr key={idx} className={isActive && idx === currentWpIdx ? 'active' : ''}>
              <td>{idx + 1}</td>
              <td>{idx < currentWpIdx ? '✓' : ''}</td>
              <td>{normalizeLat(Number(wp.lat)).toFixed(15)}</td>
              <td>{normalizeLng(Number(wp.lon)).toFixed(15)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <table className="info-table">
        <tbody>
          <tr>
            <td>Target point</td>
            <td>
              {target
                ? `${fmtLatLon(normalizeLat(Number(target.lat)))}, ${fmtLatLon(normalizeLng(Number(target.lon)))}`
                : 'Unavaliable'}
          </td>
        </tr>
        <tr>
          <td>Distance (m)</td>
          <td>{remaining !== null ? remaining.toFixed(2) : 'Unavaliable'}</td>
        </tr>
      </tbody>
    </table>
  </div>
  );
}
