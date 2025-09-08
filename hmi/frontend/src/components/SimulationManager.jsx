import { useState } from 'react';

const waves = {
  none: { amp: 0.0, freq: 0.0, spike_prob: 0.0, spike_amp: 0.0 },
  calm: { amp: 0.5, freq: 0.2, spike_prob: 0.0, spike_amp: 0.0 },
  choppy: { amp: 10.0, freq: 0.5, spike_prob: 0.01, spike_amp: 5.0 },
  moderate: { amp: 15.0, freq: 0.5, spike_prob: 0.02, spike_amp: 10.0 },
  rough: { amp: 27.5, freq: 0.7, spike_prob: 0.05, spike_amp: 15.0 },
  storm: { amp: 45.0, freq: 1.0, spike_prob: 0.1, spike_amp: 25.0 },
};

export default function SimulationManager({ missions = {} }) {
  const [routeName, setRouteName] = useState('');
  const [gpsLat, setGpsLat] = useState('0.0000000000000');
  const [gpsLon, setGpsLon] = useState('0.0000000000000');
  const [gpsHdg, setGpsHdg] = useState('0');
  const [gpsSpd, setGpsSpd] = useState('0');
  const [gpsActive, setGpsActive] = useState(false);
  const [gpsMode, setGpsMode] = useState(null); // 'ROUTE' or 'VECTOR'

  const [wave, setWave] = useState('none');
  const [imuActive, setImuActive] = useState(false);

  const missionNames = Object.keys(missions);

  const sendGps = async (payload) => {
    await fetch('/sim/gps', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  };

  const sendImu = async (payload) => {
    await fetch('/sim/imu', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  };

  const handleFollowRoute = async () => {
    const pts = missions[routeName];
    if (!pts || pts.length < 2) return;
    const payload = {
      lat: Number(pts[0].lat),
      lon: Number(pts[0].lon),
      hdg: -1,
      spd: parseFloat(gpsSpd) || 0,
      next_lat: Number(pts[1].lat),
      next_lon: Number(pts[1].lon),
      control: 'ROUTE',
    };
    await sendGps(payload);
    setGpsActive(true);
    setGpsMode('ROUTE');
    setGpsLat(String(pts[0].lat));
    setGpsLon(String(pts[0].lon));
  };

  const handleStartVector = async () => {
    const payload = {
      lat: parseFloat(gpsLat) || 0,
      lon: parseFloat(gpsLon) || 0,
      hdg: parseFloat(gpsHdg) || 0,
      spd: parseFloat(gpsSpd) || 0,
      next_lat: -1,
      next_lon: -1,
      control: 'VECTOR',
    };
    await sendGps(payload);
    setGpsActive(true);
    setGpsMode('VECTOR');
  };

  const handleStopGps = async () => {
    const payload = {
      lat: parseFloat(gpsLat) || 0,
      lon: parseFloat(gpsLon) || 0,
      hdg: -1,
      spd: 0,
      next_lat: -1,
      next_lon: -1,
      control: 'STOP',
    };
    await sendGps(payload);
    setGpsActive(false);
    setGpsMode(null);
  };

  const updateGps = async () => {
    if (!gpsActive) return;
    const payload = {
      lat: parseFloat(gpsLat) || 0,
      lon: parseFloat(gpsLon) || 0,
      hdg: gpsMode === 'ROUTE' ? -1 : parseFloat(gpsHdg) || 0,
      spd: parseFloat(gpsSpd) || 0,
      next_lat: -1,
      next_lon: -1,
      control: gpsMode || 'VECTOR',
    };
    await sendGps(payload);
  };

  const toggleImu = async () => {
    const payload = { ...waves[wave], control: imuActive ? 'STOP' : 'START' };
    await sendImu(payload);
    setImuActive((a) => !a);
  };

  const gpsStatus = gpsActive
    ? gpsMode === 'ROUTE'
      ? 'Active (Follow route)'
      : 'Active (Vector mode)'
    : 'Inactive';
  const imuStatus = imuActive ? 'Active' : 'Inactive';

  return (
    <div className="simulation-manager">
      <div className="sim-section">
        <h3>GPS Simulation</h3>
        <div>
          <select value={routeName} onChange={(e) => setRouteName(e.target.value)}>
            <option value="">Select route</option>
            {missionNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
        <div className="field-row">
          <label>Lat</label>
          <input
            type="text"
            value={gpsLat}
            onChange={(e) => setGpsLat(e.target.value)}
          />
          <button onClick={updateGps}>Update</button>
        </div>
        <div className="field-row">
          <label>Lon</label>
          <input
            type="text"
            value={gpsLon}
            onChange={(e) => setGpsLon(e.target.value)}
          />
        </div>
        <div className="field-row">
          <label>HDG</label>
          <input
            type="text"
            placeholder="Deg"
            value={gpsHdg}
            onChange={(e) => setGpsHdg(e.target.value)}
          />
          <button onClick={updateGps}>Update</button>
        </div>
        <div className="field-row">
          <label>SPD</label>
          <input
            type="text"
            placeholder="m/s"
            value={gpsSpd}
            onChange={(e) => setGpsSpd(e.target.value)}
          />
          <button onClick={updateGps}>Update</button>
        </div>
        <div>Status: {gpsStatus}</div>
        <div className="button-row">
          <button onClick={handleFollowRoute} disabled={gpsActive}>
            Follow Route
          </button>
          <button onClick={handleStartVector} disabled={gpsActive}>
            Start Vector
          </button>
          <button onClick={handleStopGps} disabled={!gpsActive}>
            Stop
          </button>
        </div>
      </div>
      <div className="sim-section">
        <h3>IMU Simulation</h3>
        <div>
          <select value={wave} onChange={(e) => setWave(e.target.value)}>
            {Object.keys(waves).map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
        <div>Status: {imuStatus}</div>
        <div>
          <button onClick={toggleImu}>{imuActive ? 'Stop' : 'Run'}</button>
        </div>
      </div>
    </div>
  );
}

