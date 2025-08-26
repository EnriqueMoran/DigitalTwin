import { useEffect, useState } from 'react';

export default function MissionsManagerViewer({ missions = {}, setMissions = () => {} }) {
  const [selected, setSelected] = useState('');
  const [waypoints, setWaypoints] = useState([]);
  const [showNameDialog, setShowNameDialog] = useState(false);
  const [newName, setNewName] = useState('');
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const missionNames = Object.keys(missions);

  useEffect(() => {
    if (selected && missions[selected]) {
      setWaypoints(
        missions[selected].map((wp) => ({
          lat: Number(wp.lat).toFixed(13),
          lon: Number(wp.lon).toFixed(13),
        }))
      );
    } else {
      setWaypoints([]);
    }
  }, [selected, missions]);

  const updateWaypoint = (idx, field, value) => {
    const updated = waypoints.map((wp, i) => (i === idx ? { ...wp, [field]: value } : wp));
    setWaypoints(updated);
  };

  const addWaypoint = () => {
    setWaypoints([...waypoints, { lat: '0.0000000000000', lon: '0.0000000000000' }]);
  };

  const saveMission = () => {
    if (!selected) {
      setNewName('');
      setShowNameDialog(true);
      return;
    }
    const converted = waypoints.map((wp) => ({ lat: parseFloat(wp.lat), lon: parseFloat(wp.lon) }));
    setMissions({ ...missions, [selected]: converted });
  };

  const confirmNewMission = () => {
    if (!newName.trim()) return;
    const converted = waypoints.map((wp) => ({ lat: parseFloat(wp.lat), lon: parseFloat(wp.lon) }));
    setMissions({ ...missions, [newName]: converted });
    setSelected(newName);
    setShowNameDialog(false);
  };

  const deleteMission = () => {
    if (!selected) return;
    setShowDeleteDialog(true);
  };

  const confirmDelete = () => {
    const updated = { ...missions };
    delete updated[selected];
    setMissions(updated);
    setSelected('');
    setWaypoints([]);
    setShowDeleteDialog(false);
  };

  return (
    <div className="mission-manager">
      <div className="controls">
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">Select mission</option>
          {missionNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <button
          onClick={() => {
            setSelected('');
            setWaypoints([]);
          }}
        >
          New Mission
        </button>
        <button onClick={saveMission}>Save</button>
        <button onClick={deleteMission} disabled={!selected}>
          Delete
        </button>
      </div>

      <table className="mission-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Lat</th>
            <th>Lon</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {waypoints.map((wp, idx) => (
            <tr key={idx}>
              <td>{idx + 1}</td>
              <td>
                <input
                  type="number"
                  value={wp.lat}
                  step="0.0000000000001"
                  onChange={(e) => updateWaypoint(idx, 'lat', e.target.value)}
                />
              </td>
              <td>
                <input
                  type="number"
                  value={wp.lon}
                  step="0.0000000000001"
                  onChange={(e) => updateWaypoint(idx, 'lon', e.target.value)}
                />
              </td>
              <td>
                <button onClick={() => setWaypoints(waypoints.filter((_, i) => i !== idx))}>🗑️</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div>
        <button onClick={addWaypoint}>Add Waypoint</button>
      </div>

      {showNameDialog && (
        <div className="overlay">
          <div className="dialog">
            <p>Enter mission name:</p>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} />
            <div className="dialog-buttons">
              <button onClick={confirmNewMission}>Confirm</button>
              <button onClick={() => setShowNameDialog(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {showDeleteDialog && (
        <div className="overlay">
          <div className="dialog">
            <p>Do you want to delete the mission?</p>
            <div className="dialog-buttons">
              <button onClick={confirmDelete}>Yes</button>
              <button onClick={() => setShowDeleteDialog(false)}>No</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

