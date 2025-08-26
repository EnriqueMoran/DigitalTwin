export default function CurrentMissionViewer({
  sensors = {},
  missions = {},
  currentMission,
  selectedMission = '',
  setSelectedMission = () => {},
  startMission = () => {},
  cancelMission = () => {},
  currentWpIdx = 0,
  mode = 'Manual',
}) {
  const selected = selectedMission || '';

  const missionNames = Object.keys(missions);
  const waypoints = selected ? missions[selected] || [] : [];

  const isActive = mode === 'Mission' && currentMission === selected;

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
    if (v === undefined || v === null) return 'Null';
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
  const remaining =
    target && sensors.gps_latitude !== undefined && sensors.gps_longitude !== undefined
      ? haversine(
          sensors.gps_latitude,
          sensors.gps_longitude,
          Number(target.lat),
          Number(target.lon)
        )
      : null;

  const handleAction = () => {
    if (isActive) cancelMission();
    else if (selected) startMission(selected);
  };

  return (
    <div className="current-mission">
      <div className="controls">
        <select value={selected} onChange={(e) => setSelectedMission(e.target.value)}>
          <option value="">Select mission</option>
          {missionNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <button onClick={handleAction} disabled={!selected && !isActive}>
          {isActive ? 'Abort Mission' : 'Start Mission'}
        </button>
      </div>

      <table className="mission-table">
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
              <td>{Number(wp.lat).toFixed(13)}</td>
              <td>{Number(wp.lon).toFixed(13)}</td>
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
                ? `${fmtLatLon(Number(target.lat))}, ${fmtLatLon(Number(target.lon))}`
                : 'Null'}
            </td>
          </tr>
          <tr>
            <td>Remaining distance (m)</td>
            <td>{remaining !== null ? remaining.toFixed(2) : 'Null'}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

