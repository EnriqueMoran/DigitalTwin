import { useEffect, useState, useRef } from 'react';
import { resetSimState } from '../state/simStore';
import BoatViewer from '../components/BoatViewer';
import MapPanel from '../components/MapPanel';
import RadarViewer from '../components/RadarViewer';
import CurrentRouteViewer from '../components/CurrentRouteViewer';
import RoutesManagerViewer from '../components/RoutesManagerViewer';
import CamerasViewer from '../components/CamerasViewer';
import SensorData from '../components/SensorData';
import SystemStatus from '../components/SystemStatus';
import Widgets from '../components/Widgets';
import SimulationManager from '../components/SimulationManager';
import RecordingManager from '../components/RecordingManager';

const ROUTE_THRESHOLD = 2; // meters

const panelOptions = [
  { value: '3d', label: '3D Model', component: BoatViewer },
  { value: 'gps', label: 'GPS View', component: MapPanel },
  { value: 'radar', label: 'Radar View', component: RadarViewer },
  { value: 'currentRoute', label: 'Current Route View', component: CurrentRouteViewer },
  { value: 'routesManager', label: 'Routes Manager', component: RoutesManagerViewer },
 // { value: 'cameras', label: 'Onboard Cameras', component: CamerasViewer },
  { value: 'sensorData', label: 'Sensor Data', component: SensorData },
  { value: 'systemStatus', label: 'System Status', component: SystemStatus },
  { value: 'widgets', label: 'Widgets View', component: Widgets },
  { value: 'simulationManager', label: 'Simulation Manager', component: SimulationManager },
  { value: 'recordingManager', label: 'Recording Manager', component: RecordingManager },
];

// Options sorted alphabetically by label for the dropdowns
const sortedPanelOptions = [...panelOptions].sort((a, b) => a.label.localeCompare(b.label));

export default function MainScreen({ sensors }) {
  const [leftPanel, setLeftPanel] = useState('3d');
  const [rightPanel, setRightPanel] = useState('gps');
  const [bottomLeftPanel, setBottomLeftPanel] = useState('systemStatus');
  const [bottomCenterPanel, setBottomCenterPanel] = useState('sensorData');
  const [bottomRightPanel, setBottomRightPanel] = useState('widgets');
  const deriveApiBase = () => {
    try {
      const proto = window?.location?.protocol || 'http:';
      const host = window?.location?.hostname || 'localhost';
      return `${proto}//${host}:8001`;
    } catch (_) {
      return 'http://localhost:8001';
    }
  };
  const API_BASE = (import.meta && import.meta.env && import.meta.env.VITE_BACKEND_HTTP) || deriveApiBase();
  const [routesState, setRoutesState] = useState({});
  const [mode, setMode] = useState('Manual');
  const [currentRoute, setCurrentRoute] = useState(null);
  const [currentWpIdx, setCurrentWpIdx] = useState(0);
  const [gpsTrail, setGpsTrail] = useState([]);
  const [selectedRoute, setSelectedRoute] = useState('');
  const prevGpsPos = useRef(gpsTrail[gpsTrail.length - 1] || null);

  const setRoutes = (m) => {
    // Deprecated: routes are now server-side. No-op here.
    setRoutesState(m);
  };

  // Persist UI state server-side when changed
  useEffect(() => {
    fetch(`${API_BASE}/ui_state`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }) }).catch(() => {});
  }, [mode]);
  useEffect(() => {
    fetch(`${API_BASE}/ui_state`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ currentRoute }) }).catch(() => {});
  }, [currentRoute]);
  useEffect(() => {
    fetch(`${API_BASE}/ui_state`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ currentWpIdx }) }).catch(() => {});
  }, [currentWpIdx]);

  const prevUptime = useRef(null);
  useEffect(() => {
    const uptime = sensors.uptime;
    if (uptime == null) return;
    const prev = prevUptime.current;
    if (prev != null && uptime < prev) {
      resetSimState();
    }
    prevUptime.current = uptime;
  }, [sensors.uptime]);

  // Poll routes from backend so they are shared and coherent across sessions
  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch(`${API_BASE}/routes`).then(r => r.json()).then(d => {
        if (!cancelled && d && d.routes && typeof d.routes === 'object') {
          setRoutesState(d.routes);
        }
      }).catch(() => {});
    };
    load();
    const id = setInterval(load, 1000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // One-time migration: if server has no routes, push any local routes to server
  useEffect(() => {
    try {
      const local = JSON.parse(localStorage.getItem('routes') || '{}');
      const names = Object.keys(local || {});
      if (!names.length) return;
      // If current server state is non-empty, skip migration
      if (routesState && Object.keys(routesState).length > 0) return;
      names.forEach((name) => {
        const pts = Array.isArray(local[name]) ? local[name] : [];
        fetch(`${API_BASE}/routes`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, points: pts }),
        }).catch(() => {});
      });
    } catch (_) {}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll UI state and trail from backend so all sessions stay consistent
  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch(`${API_BASE}/ui_state`).then(r => r.json()).then(s => {
        if (cancelled) return;
        if (typeof s.mode === 'string') setMode(s.mode);
        setCurrentRoute(s.currentRoute ?? null);
        setCurrentWpIdx(Number.isFinite(Number(s.currentWpIdx)) ? Number(s.currentWpIdx) : 0);
      }).catch(() => {});
      fetch(`${API_BASE}/trail`).then(r => r.json()).then(d => {
        if (cancelled) return;
        const pts = Array.isArray(d.points) ? d.points : [];
        setGpsTrail(pts);
      }).catch(() => {});
    };
    load();
    const id = setInterval(load, 1000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  useEffect(() => {
    if (!String(mode).startsWith('Route') || !currentRoute) return;
    const route = routesState[currentRoute];
    if (!route || route.length === 0) {
      setMode('Manual');
      setCurrentRoute(null);
      return;
    }
    const latRaw =
      sensors.gps_latitude ?? sensors.latitude ?? sensors.lat ?? sensors.y ?? null;
    const lonRaw =
      sensors.gps_longitude ??
      sensors.longitude ??
      sensors.lon ??
      sensors.lng ??
      sensors.long ??
      null;
    const normalizeLng = (lng) => ((lng + 180) % 360 + 360) % 360 - 180;
    const normalizeLat = (lat) => Math.max(-90, Math.min(90, lat));
    const lat = latRaw == null ? NaN : Number(latRaw);
    const lon = lonRaw == null ? NaN : Number(lonRaw);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
    const wp = route[currentWpIdx];
    const dist = haversine(
      normalizeLat(lat),
      normalizeLng(lon),
      normalizeLat(Number(wp.lat)),
      normalizeLng(Number(wp.lon))
    );
    if (dist <= ROUTE_THRESHOLD) {
      if (currentWpIdx + 1 >= route.length) {
        setMode('Manual');
        setCurrentRoute(null);
        setCurrentWpIdx(0);
      } else {
        setCurrentWpIdx((i) => i + 1);
      }
    }
  }, [sensors, mode, currentRoute, currentWpIdx, routesState]);

  useEffect(() => {
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
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || (lat === 0 && lon === 0))
      return;
    const pos = [lat, lon];
    const prev = prevGpsPos.current;
    if (!prev || prev[0] !== pos[0] || prev[1] !== pos[1]) {
      fetch(`${API_BASE}/trail/append`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lat, lon }) }).catch(() => {});
      prevGpsPos.current = pos;
    }
  }, [sensors]);

  const startRoute = (name) => {
    if (!routesState[name]) return;
    setCurrentRoute(name);
    setCurrentWpIdx(0);
    setMode('Route (Manual)');
  };

  const cancelRoute = () => {
    setMode('Manual');
    setCurrentRoute(null);
    setCurrentWpIdx(0);
  };

  const sensorsWithMode = { ...sensors, mode };

  const renderPanel = (value) => {
    const opt = panelOptions.find((o) => o.value === value);
    if (!opt) return null;
    const Comp = opt.component;
    return (
      <Comp
        sensors={sensorsWithMode}
        mode={mode}
        routes={routesState}
        setRoutes={setRoutes}
        currentRoute={currentRoute}
        startRoute={startRoute}
        cancelRoute={cancelRoute}
        currentWpIdx={currentWpIdx}
        trail={gpsTrail}
        selectedRoute={selectedRoute}
        setSelectedRoute={setSelectedRoute}
        clearTrail={() => { fetch(`${API_BASE}/trail/clear`, { method: 'POST' }).catch(() => {}); setGpsTrail([]); }}
      />
    );
  };

  return (
    <div className="main-screen">
      <div className="top-panels">
        <div className="panel-container">
          <select value={leftPanel} onChange={(e) => setLeftPanel(e.target.value)}>
            {sortedPanelOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <div className="panel">{renderPanel(leftPanel)}</div>
        </div>
        <div className="panel-container">
          <select value={rightPanel} onChange={(e) => setRightPanel(e.target.value)}>
            {sortedPanelOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <div className="panel">{renderPanel(rightPanel)}</div>
        </div>
      </div>
      <div className="bottom-panels">
        <div className="panel-container">
          <select value={bottomLeftPanel} onChange={(e) => setBottomLeftPanel(e.target.value)}>
            {sortedPanelOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <div className="panel">{renderPanel(bottomLeftPanel)}</div>
        </div>
        <div className="panel-container">
          <select value={bottomCenterPanel} onChange={(e) => setBottomCenterPanel(e.target.value)}>
            {sortedPanelOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <div className="panel">{renderPanel(bottomCenterPanel)}</div>
        </div>
        <div className="panel-container">
          <select value={bottomRightPanel} onChange={(e) => setBottomRightPanel(e.target.value)}>
            {sortedPanelOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <div className="panel">{renderPanel(bottomRightPanel)}</div>
        </div>
      </div>
    </div>
  );
}

function haversine(lat1, lon1, lat2, lon2) {
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
}
