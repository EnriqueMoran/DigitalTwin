import React, { useEffect } from 'react';
import { useSimStore, setSimState } from '../state/simStore';

const deriveApiBase = () => {
  try {
    const proto = window?.location?.protocol || 'http:';
    const host = window?.location?.hostname || 'localhost';
    const port = '8001';
    return `${proto}//${host}:${port}`;
  } catch (_) {
    return 'http://localhost:8001';
  }
};
const API_BASE = import.meta.env.VITE_BACKEND_HTTP || deriveApiBase();

const waves = {
  calm: { amp: 0.5,  freq: 0.2,  spike_prob: 0.0,   spike_amp: 0.0 },
  choppy: { amp: 6.0,  freq: 0.45, spike_prob: 0.008, spike_amp: 3.0 },
  moderate: { amp: 8.0,  freq: 0.50, spike_prob: 0.010, spike_amp: 4.0 },
  rough: { amp: 12.0, freq: 0.60, spike_prob: 0.020, spike_amp: 6.0 },
  storm: { amp: 18.0, freq: 0.80, spike_prob: 0.030, spike_amp: 8.0 },
};

export default function SimulationManager({ routes = {}, sensors = {}, clearTrail = undefined }) {
  const normalizeLng = (lng) => {
    if (!Number.isFinite(lng)) return lng;
    return ((lng + 180) % 360 + 360) % 360 - 180;
  };
  const normalizeLat = (lat) => {
    if (!Number.isFinite(lat)) return lat;
    return Math.max(-90, Math.min(90, lat));
  };
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

  const routeNames = Object.keys(routes);

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

  // When following a route, automatically advance target and adjust heading
  useEffect(() => {
    if (!gpsActive || gpsMode !== 'ROUTE') return;
    const pts = routes[routeName];
    if (!pts || pts.length < 2) return;

    // Current position from sensors
    const sLatRaw = sensors?.gps_latitude ?? sensors?.latitude ?? sensors?.lat ?? sensors?.y ?? null;
    const sLonRaw = sensors?.gps_longitude ?? sensors?.longitude ?? sensors?.lon ?? sensors?.lng ?? sensors?.long ?? null;
    const latCurRaw = sLatRaw == null ? NaN : Number(sLatRaw);
    const lonCurRaw = sLonRaw == null ? NaN : Number(sLonRaw);
    if (!Number.isFinite(latCurRaw) || !Number.isFinite(lonCurRaw)) return;
    const latCur = normalizeLat(latCurRaw);
    const lonCur = normalizeLng(lonCurRaw);

    // Determine current target index based on routeNextLat/Lon stored
    const tol = 1e-6; // ~0.1m in lat/lon; good enough to match
    let idx = -1;
    for (let i = 0; i < pts.length; i++) {
      if (Math.abs(Number(pts[i].lat) - routeNextLat) <= tol && Math.abs(Number(pts[i].lon) - routeNextLon) <= tol) {
        idx = i; break;
      }
    }
    // If unknown, assume next is the second waypoint
    if (idx < 0) idx = Math.min(1, pts.length - 1);

    const targetLat = normalizeLat(Number(pts[idx].lat));
    const targetLon = normalizeLng(Number(pts[idx].lon));

    // Distance to current target
    const R = 6371000;
    const toRad = (d) => (d * Math.PI) / 180;
    const dLat = toRad(targetLat - latCur);
    const dLon = toRad(targetLon - lonCur);
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(latCur)) * Math.cos(toRad(targetLat)) * Math.sin(dLon / 2) ** 2;
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const dist = R * c;

    const ADV_THR = 2; // meters
    if (dist <= ADV_THR) {
      // Move to next target or stop if route finished
      const nextIdx = idx + 1;
      if (nextIdx >= pts.length) {
        // End of route -> stop
        (async () => {
          try {
            await sendGps({ lat: latCur, lon: lonCur, hdg: -1, spd: 0, next_lat: -1, next_lon: -1, control: 'STOP' });
          } catch (_) {}
        })();
        setSimState({ gpsActive: false, gpsMode: null, routeNextLat: -1, routeNextLon: -1 });
        return;
      }

      const nextLat = normalizeLat(Number(pts[nextIdx].lat));
      const nextLon = normalizeLng(Number(pts[nextIdx].lon));
      (async () => {
        try {
          await sendGps({ lat: latCur, lon: lonCur, hdg: -1, spd: parseFloat(gpsSpd) || 0, next_lat: nextLat, next_lon: nextLon, control: 'ROUTE' });
        } catch (_) {}
      })();
      setSimState({ routeNextLat: nextLat, routeNextLon: nextLon });
    }
  }, [gpsActive, gpsMode, routeName, routes, sensors?.latitude, sensors?.gps_latitude, sensors?.longitude, sensors?.gps_longitude, routeNextLat, routeNextLon, gpsSpd]);

  const handleFollowRoute = async () => {
    const pts = routes[routeName];
    if (!pts || pts.length < 2) return;
    // Clear trail when starting a new Follow Route
    try { if (typeof clearTrail === 'function') clearTrail(); } catch (_) {}
    const payload = {
      lat: normalizeLat(Number(pts[0].lat)),
      lon: normalizeLng(Number(pts[0].lon)),
      hdg: -1,
      spd: parseFloat(gpsSpd) || 0,
      next_lat: normalizeLat(Number(pts[1].lat)),
      next_lon: normalizeLng(Number(pts[1].lon)),
      control: 'ROUTE',
    };
    await sendGps(payload);
    setSimState({
      gpsActive: true,
      gpsMode: 'ROUTE',
      gpsLat: String(payload.lat),
      gpsLon: String(payload.lon),
      routeNextLat: payload.next_lat,
      routeNextLon: payload.next_lon,
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
    const latCurRaw = Number.isFinite(latFromSensors) ? latFromSensors : lat;
    const lonCurRaw = Number.isFinite(lonFromSensors) ? lonFromSensors : lon;
    const latCur = normalizeLat(latCurRaw);
    const lonCur = normalizeLng(lonCurRaw);
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
            const pts = routes[routeName];
            if (pts && pts.length >= 2) {
              next_lat = normalizeLat(Number(pts[1].lat));
              next_lon = normalizeLng(Number(pts[1].lon));
            }
          }
        }
        await sendGps({ lat: latCur, lon: lonCur, hdg: gpsMode === 'ROUTE' ? -1 : hdg, spd, next_lat, next_lon, control: gpsMode });
      }
      return;
    }

    if (type === 'hdg') {
      // Heading update => if ROUTE switch to VECTOR and continue from current position; if VECTOR just update heading
      if (gpsActive) {
        if (gpsMode === 'ROUTE') {
          await sendGps({ lat: latCur, lon: lonCur, hdg, spd, next_lat: -1, next_lon: -1, control: 'VECTOR' });
          setSimState({ gpsMode: 'VECTOR', routeNextLat: -1, routeNextLon: -1 });
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
          <select
            style={{ width: 220 }}
            value={routeName}
            onChange={(e) => {
              const name = e.target.value;
              const patch = { routeName: name };
              const pts = routes[name];
              if (Array.isArray(pts) && pts.length > 0) {
                const lat0 = Number(pts[0].lat);
                const lon0 = Number(pts[0].lon);
                if (Number.isFinite(lat0) && Number.isFinite(lon0)) {
                  patch.gpsLat = String(lat0);
                  patch.gpsLon = String(lon0);
                }
              }
              setSimState(patch);
            }}
          >
            <option value="">Select route</option>
            {routeNames.map((name) => (
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
            style={{ width: 110 }}
            value={gpsLat}
            onChange={(e) => setSimState({ gpsLat: e.target.value })}
          />
          <button onClick={() => updateGps('pos')}>Update</button>
        </div>
        <div className="field-row">
          <label>Lon</label>
          <input
            type="text"
            style={{ width: 110 }}
            value={gpsLon}
            onChange={(e) => setSimState({ gpsLon: e.target.value })}
          />
        </div>
        <div className="field-row">
          <label>HDG</label>
          <input
            type="text"
            placeholder="Deg"
            style={{ width: 110 }}
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
            style={{ width: 110 }}
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
          <select
            value={wave}
            onChange={async (e) => {
              const val = e.target.value;
              setSimState({ wave: val });
              // If IMU is running, update wave parameters live without restart
              if (imuActive) {
                try { await sendImu({ ...waves[val] }); } catch (_) {}
              }
            }}
          >
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
