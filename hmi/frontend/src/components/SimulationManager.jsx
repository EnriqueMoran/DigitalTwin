import React from 'react';
import { useSimStore, setSimState } from '../state/simStore';

const API_BASE = import.meta.env.VITE_BACKEND_HTTP || 'http://localhost:8001';

const waves = {
  calm: { amp: 0.5, freq: 0.2, spike_prob: 0.0, spike_amp: 0.0 },
  choppy: { amp: 10.0, freq: 0.5, spike_prob: 0.01, spike_amp: 5.0 },
  moderate: { amp: 15.0, freq: 0.5, spike_prob: 0.02, spike_amp: 10.0 },
  rough: { amp: 27.5, freq: 0.7, spike_prob: 0.05, spike_amp: 15.0 },
  storm: { amp: 45.0, freq: 1.0, spike_prob: 0.1, spike_amp: 25.0 },
};

export default function SimulationManager({ missions = {}, sensors = {} }) {
  const {
    routeName,
    gpsLat,
    gpsLon,
    gpsHdg,
    gpsSpd,
    gpsActive,
    gpsMode,
    routeNextLat,
    routeNextLon,
    wave,
    imuActive,
  } = useSimStore((s) => ({
    routeName: s.routeName,
    gpsLat: s.gpsLat,
    gpsLon: s.gpsLon,
    gpsHdg: s.gpsHdg,
    gpsSpd: s.gpsSpd,
    gpsActive: s.gpsActive,
    gpsMode: s.gpsMode,
    routeNextLat: s.routeNextLat,
    routeNextLon: s.routeNextLon,
    wave: s.wave,
    imuActive: s.imuActive,
  }));

  const missionNames = Object.keys(missions);

  const sendGps = async (payload) => {
    const withHeading = { ...payload };
    if (withHeading.hdg !== undefined && withHeading.hdg !== null) {
      withHeading.heading = withHeading.hdg;
    }
    await fetch(`${API_BASE}/sim/gps`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(withHeading),
    });
  };

  const sendImu = async (payload) => {
    await fetch(`${API_BASE}/sim/imu`, {
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
    setSimState({
      gpsActive: true,
      gpsMode: 'ROUTE',
      gpsLat: String(pts[0].lat),
      gpsLon: String(pts[0].lon),
      routeNextLat: Number(pts[1].lat),
      routeNextLon: Number(pts[1].lon),
    });
  };

  const handleStartVector = async () => {
    let latVal = parseFloat(gpsLat);
    let lonVal = parseFloat(gpsLon);
    const sLat = Number(sensors.latitude);
    const sLon = Number(sensors.longitude);
    if (!Number.isFinite(latVal)) latVal = 0;
    if (!Number.isFinite(lonVal)) lonVal = 0;
    if ((latVal === 0 && lonVal === 0) && Number.isFinite(sLat) && Number.isFinite(sLon) && (sLat !== 0 || sLon !== 0)) {
      latVal = sLat;
      lonVal = sLon;
      setSimState({ gpsLat: String(latVal.toFixed(12)), gpsLon: String(lonVal.toFixed(12)) });
    }
    const payload = {
      lat: latVal || 0,
      lon: lonVal || 0,
      hdg: parseFloat(gpsHdg) || 0,
      spd: parseFloat(gpsSpd) || 0,
      next_lat: -1,
      next_lon: -1,
      control: 'VECTOR',
    };
    await sendGps(payload);
    setSimState({ gpsActive: true, gpsMode: 'VECTOR', routeNextLat: -1, routeNextLon: -1 });
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
    setSimState({ gpsActive: false, gpsMode: null, routeNextLat: -1, routeNextLon: -1 });
  };

  const updateGps = async (type) => {
    // Always use current position from sensors for spd/hdg updates to avoid jumps
    const sLatRaw = sensors?.gps_latitude ?? sensors?.latitude ?? sensors?.lat ?? sensors?.y ?? null;
    const sLonRaw = sensors?.gps_longitude ?? sensors?.longitude ?? sensors?.lon ?? sensors?.lng ?? sensors?.long ?? null;
    const latFromSensors = sLatRaw == null ? NaN : Number(sLatRaw);
    const lonFromSensors = sLonRaw == null ? NaN : Number(sLonRaw);
    const lat = parseFloat(gpsLat) || 0;
    const lon = parseFloat(gpsLon) || 0;
    const latCur = Number.isFinite(latFromSensors) ? latFromSensors : lat;
    const lonCur = Number.isFinite(lonFromSensors) ? lonFromSensors : lon;
    const hdg = parseFloat(gpsHdg) || 0;
    const spd = parseFloat(gpsSpd) || 0;

    if (type === 'pos') {
      // Position update => stop simulation
      if (gpsActive) {
        await sendGps({
          lat,
          lon,
          hdg: gpsMode === 'ROUTE' ? -1 : hdg,
          spd: 0,
          next_lat: -1,
          next_lon: -1,
          control: 'STOP',
        });
      }
      setSimState({ gpsActive: false, gpsMode: null, routeNextLat: -1, routeNextLon: -1 });
      return;
    }

    if (type === 'spd') {
      // Speed update => keep running and adapt speed
      if (gpsActive && gpsMode) {
        let next_lat = -1;
        let next_lon = -1;
        if (gpsMode === 'ROUTE') {
          if (Number.isFinite(routeNextLat) && Number.isFinite(routeNextLon) && routeNextLat !== -1 && routeNextLon !== -1) {
            next_lat = routeNextLat;
            next_lon = routeNextLon;
          } else {
            const pts = missions[routeName];
            if (pts && pts.length >= 2) {
              next_lat = Number(pts[1].lat);
              next_lon = Number(pts[1].lon);
            }
          }
        }
        await sendGps({ lat: latCur, lon: lonCur, hdg: gpsMode === 'ROUTE' ? -1 : hdg, spd, next_lat, next_lon, control: gpsMode });
      }
      return;
    }

    if (type === 'hdg') {
      // Heading update => if ROUTE then stop; if VECTOR update heading
      if (gpsActive) {
        if (gpsMode === 'ROUTE') {
          await sendGps({ lat, lon, hdg: -1, spd: 0, next_lat: -1, next_lon: -1, control: 'STOP' });
          setSimState({ gpsActive: false, gpsMode: null });
        } else {
          await sendGps({ lat: latCur, lon: lonCur, hdg, spd, next_lat: -1, next_lon: -1, control: 'VECTOR' });
        }
      }
      return;
    }
  };

  const toggleImu = async () => {
    const payload = { ...waves[wave], control: imuActive ? 'STOP' : 'START' };
    await sendImu(payload);
    setSimState({ imuActive: !imuActive });
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
          <select value={routeName} onChange={(e) => setSimState({ routeName: e.target.value })}>
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
            onChange={(e) => setSimState({ gpsLat: e.target.value })}
          />
          <button onClick={() => updateGps('pos')}>Update</button>
        </div>
        <div className="field-row">
          <label>Lon</label>
          <input
            type="text"
            value={gpsLon}
            onChange={(e) => setSimState({ gpsLon: e.target.value })}
          />
        </div>
        <div className="field-row">
          <label>HDG</label>
          <input
            type="text"
            placeholder="Deg"
            value={gpsHdg}
            onChange={(e) => setSimState({ gpsHdg: e.target.value })}
          />
          <button onClick={() => updateGps('hdg')}>Update</button>
        </div>
        <div className="field-row">
          <label>SPD</label>
          <input
            type="text"
            placeholder="m/s"
            value={gpsSpd}
            onChange={(e) => setSimState({ gpsSpd: e.target.value })}
          />
          <button onClick={() => updateGps('spd')}>Update</button>
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
          <select value={wave} onChange={(e) => setSimState({ wave: e.target.value })}>
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
