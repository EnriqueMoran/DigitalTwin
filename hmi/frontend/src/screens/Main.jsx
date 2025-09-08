import { useEffect, useState, useRef } from 'react';
import { resetSimState } from '../state/simStore';
import BoatViewer from '../components/BoatViewer';
import MapPanel from '../components/MapPanel';
import RadarViewer from '../components/RadarViewer';
import CurrentMissionViewer from '../components/CurrentMissionViewer';
import MissionsManagerViewer from '../components/MissionsManagerViewer';
import CamerasViewer from '../components/CamerasViewer';
import SensorData from '../components/SensorData';
import SystemStatus from '../components/SystemStatus';
import Widgets from '../components/Widgets';
import SimulationManager from '../components/SimulationManager';

const MISSION_THRESHOLD = 35; // meters

const panelOptions = [
  { value: '3d', label: '3D Model', component: BoatViewer },
  { value: 'gps', label: 'GPS', component: MapPanel },
  { value: 'radar', label: 'Radar', component: RadarViewer },
  { value: 'currentMission', label: 'Current Mission', component: CurrentMissionViewer },
  { value: 'missionsManager', label: 'Missions Manager', component: MissionsManagerViewer },
  { value: 'cameras', label: 'Onboard Cameras', component: CamerasViewer },
  { value: 'sensorData', label: 'Sensor Data', component: SensorData },
  { value: 'systemStatus', label: 'System Status', component: SystemStatus },
  { value: 'widgets', label: 'Widgets', component: Widgets },
  { value: 'simulationManager', label: 'Simulation Manager', component: SimulationManager },
];

// Opciones ordenadas alfabéticamente por etiqueta para los dropdowns
const sortedPanelOptions = [...panelOptions].sort((a, b) => a.label.localeCompare(b.label));

export default function MainScreen({ sensors }) {
  const [leftPanel, setLeftPanel] = useState('3d');
  const [rightPanel, setRightPanel] = useState('gps');
  const [bottomLeftPanel, setBottomLeftPanel] = useState('systemStatus');
  const [bottomCenterPanel, setBottomCenterPanel] = useState('sensorData');
  const [bottomRightPanel, setBottomRightPanel] = useState('widgets');
  const [missionsState, setMissionsState] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('missions') || '{}');
    } catch (e) {
      return {};
    }
  });
  const [mode, setMode] = useState(() => localStorage.getItem('mode') || 'Manual');
  const [currentMission, setCurrentMission] = useState(() => {
    const m = localStorage.getItem('currentMission');
    return m === '' ? null : m;
  });
  const [currentWpIdx, setCurrentWpIdx] = useState(() => {
    const idx = Number(localStorage.getItem('currentWpIdx'));
    return Number.isFinite(idx) ? idx : 0;
    
  });
  const [gpsTrail, setGpsTrail] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('gpsTrail') || '[]');
    } catch {
      return [];
    }
  });
  const [selectedMission, setSelectedMission] = useState('');
  const prevGpsPos = useRef(gpsTrail[gpsTrail.length - 1] || null);

  const setMissions = (m) => {
    setMissionsState(m);
    localStorage.setItem('missions', JSON.stringify(m));
  };

  useEffect(() => {
    localStorage.setItem('mode', mode);
  }, [mode]);

  useEffect(() => {
    localStorage.setItem('currentMission', currentMission ?? '');
  }, [currentMission]);

  useEffect(() => {
    localStorage.setItem('currentWpIdx', String(currentWpIdx));
  }, [currentWpIdx]);

  useEffect(() => {
    localStorage.setItem('gpsTrail', JSON.stringify(gpsTrail));
  }, [gpsTrail]);

  useEffect(() => {
    const uptime = sensors.uptime;
    if (uptime == null) return;
    const prev = Number(localStorage.getItem('serviceUptime') || '0');
    if (uptime < prev) {
      setMode('Manual');
      setCurrentMission(null);
      setCurrentWpIdx(0);
      setGpsTrail([]);
      localStorage.removeItem('mode');
      localStorage.removeItem('currentMission');
      localStorage.removeItem('currentWpIdx');
      localStorage.removeItem('gpsTrail');
      // Also reset simulation forms/store on service restart
      resetSimState();
    }
    localStorage.setItem('serviceUptime', String(uptime));
  }, [sensors.uptime]);

  useEffect(() => {
    if (mode !== 'Mission' || !currentMission) return;
    const mission = missionsState[currentMission];
    if (!mission || mission.length === 0) {
      setMode('Manual');
      setCurrentMission(null);
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
    const lat = latRaw == null ? NaN : Number(latRaw);
    const lon = lonRaw == null ? NaN : Number(lonRaw);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
    const wp = mission[currentWpIdx];
    const dist = haversine(lat, lon, Number(wp.lat), Number(wp.lon));
    if (dist <= MISSION_THRESHOLD) {
      if (currentWpIdx + 1 >= mission.length) {
        setMode('Manual');
        setCurrentMission(null);
        setCurrentWpIdx(0);
      } else {
        setCurrentWpIdx((i) => i + 1);
      }
    }
  }, [sensors, mode, currentMission, currentWpIdx, missionsState]);

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
      setGpsTrail((t) => [...t, pos]);
      prevGpsPos.current = pos;
    }
  }, [sensors]);

  const startMission = (name) => {
    if (!missionsState[name]) return;
    setCurrentMission(name);
    setCurrentWpIdx(0);
    setMode('Mission');
  };

  const cancelMission = () => {
    setMode('Manual');
    setCurrentMission(null);
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
        missions={missionsState}
        setMissions={setMissions}
        currentMission={currentMission}
        startMission={startMission}
        cancelMission={cancelMission}
        currentWpIdx={currentWpIdx}
        trail={gpsTrail}
        selectedMission={selectedMission}
        setSelectedMission={setSelectedMission}
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
