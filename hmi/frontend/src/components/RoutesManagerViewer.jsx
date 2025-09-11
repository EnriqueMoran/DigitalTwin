import { useEffect, useState } from 'react';

const MAX_WAYPOINTS = 10;
const DECIMALS = 15;
const emptyWaypoint = () => ({ lat: '', lon: '' });

const formatDecimals = (value) => {
  if (value === '') return '';
  const num = Number(value);
  return Number.isNaN(num) ? value : num.toFixed(DECIMALS);
};

const normalizeLng = (lng) => {
  if (!Number.isFinite(lng)) return lng;
  return ((lng + 180) % 360 + 360) % 360 - 180;
};
const normalizeLat = (lat) => {
  if (!Number.isFinite(lat)) return lat;
  return Math.max(-90, Math.min(90, lat));
};

export default function RoutesManagerViewer({ routes = {}, setRoutes = () => {} }) {
  const [selected, setSelected] = useState('');
  const [waypoints, setWaypoints] = useState(
    Array.from({ length: MAX_WAYPOINTS }, emptyWaypoint)
  );
  const [showNameDialog, setShowNameDialog] = useState(false);
  const [newName, setNewName] = useState('');
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const routeNames = Object.keys(routes);

  useEffect(() => {
    if (selected && routes[selected]) {
      const wps = Array.from({ length: MAX_WAYPOINTS }, emptyWaypoint);
      routes[selected].forEach((wp, i) => {
        if (i < MAX_WAYPOINTS) {
          wps[i] = {
            lat: normalizeLat(Number(wp.lat)).toFixed(DECIMALS),
            lon: normalizeLng(Number(wp.lon)).toFixed(DECIMALS),
          };
        }
      });
      setWaypoints(wps);
    } else {
      setWaypoints(Array.from({ length: MAX_WAYPOINTS }, emptyWaypoint));
    }
  }, [selected, routes]);

  const updateWaypoint = (idx, field, value) => {
    const updated = [...waypoints];
    updated[idx] = { ...updated[idx], [field]: value };
    setWaypoints(updated);
  };

  const clearWaypoint = (idx) => {
    const updated = [...waypoints];
    updated[idx] = emptyWaypoint();
    setWaypoints(updated);
  };

  const saveRoute = () => {
    if (!selected) {
      setNewName('');
      setShowNameDialog(true);
      return;
    }
    const converted = waypoints
      .filter((wp) => wp.lat !== '' && wp.lon !== '')
      .map((wp) => ({
        lat: normalizeLat(parseFloat(formatDecimals(wp.lat))),
        lon: normalizeLng(parseFloat(formatDecimals(wp.lon))),
      }));
    setRoutes({ ...routes, [selected]: converted });
  };

  const confirmNewRoute = () => {
    if (!newName.trim()) return;
    const converted = waypoints
      .filter((wp) => wp.lat !== '' && wp.lon !== '')
      .map((wp) => ({
        lat: normalizeLat(parseFloat(formatDecimals(wp.lat))),
        lon: normalizeLng(parseFloat(formatDecimals(wp.lon))),
      }));
    setRoutes({ ...routes, [newName]: converted });
    setSelected(newName);
    setShowNameDialog(false);
  };

  const deleteRoute = () => {
    if (!selected) return;
    setShowDeleteDialog(true);
  };

  const confirmDelete = () => {
    const updated = { ...routes };
    delete updated[selected];
    setRoutes(updated);
    setSelected('');
    setWaypoints([]);
    setShowDeleteDialog(false);
  };

  return (
    <div className="route-manager">
      <div className="controls">
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">Select route</option>
          {routeNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <button
          onClick={() => {
            setSelected('');
            setWaypoints(
              Array.from({ length: MAX_WAYPOINTS }, emptyWaypoint)
            );
          }}
        >
          New Route
        </button>
        <button onClick={saveRoute}>Save</button>
        <button onClick={deleteRoute} disabled={!selected}>
          Delete
        </button>
      </div>

      <table className="route-table">
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
                  type="text"
                  inputMode="decimal"
                  value={wp.lat}
                  onChange={(e) => updateWaypoint(idx, 'lat', e.target.value)}
                  onBlur={(e) => updateWaypoint(idx, 'lat', formatDecimals(e.target.value))}
                />
              </td>
              <td>
                <input
                  type="text"
                  inputMode="decimal"
                  value={wp.lon}
                  onChange={(e) => updateWaypoint(idx, 'lon', e.target.value)}
                  onBlur={(e) => updateWaypoint(idx, 'lon', formatDecimals(e.target.value))}
                />
              </td>
              <td>
                <button onClick={() => clearWaypoint(idx)}>🗑️</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {showNameDialog && (
        <div className="overlay">
          <div className="dialog">
            <p>Enter route name:</p>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} />
            <div className="dialog-buttons">
              <button onClick={confirmNewRoute}>Confirm</button>
              <button onClick={() => setShowNameDialog(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {showDeleteDialog && (
        <div className="overlay">
          <div className="dialog">
            <p>Do you want to delete the route?</p>
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

