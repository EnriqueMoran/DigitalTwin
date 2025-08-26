import { useEffect, useState } from 'react';

export default function CurrentMissionViewer({
  missions = {},
  currentMission,
  startMission = () => {},
  cancelMission = () => {},
  currentWpIdx = 0,
  mode = 'Manual',
}) {
  const [selected, setSelected] = useState(currentMission || '');

  useEffect(() => {
    setSelected(currentMission || '');
  }, [currentMission]);

  const missionNames = Object.keys(missions);
  const waypoints = selected ? missions[selected] || [] : [];

  const isActive = mode === 'Mission' && currentMission === selected;

  const handleAction = () => {
    if (isActive) cancelMission();
    else if (selected) startMission(selected);
  };

  return (
    <div className="current-mission">
      <div className="controls">
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
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
    </div>
  );
}

