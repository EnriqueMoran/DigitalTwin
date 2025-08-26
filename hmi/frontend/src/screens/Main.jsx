import { useEffect, useState, useRef } from 'react';
import BoatViewer from '../components/BoatViewer';
import MapPanel from '../components/MapPanel';
import RadarViewer from '../components/RadarViewer';
import CurrentMissionViewer from '../components/CurrentMissionViewer';
import MissionsManagerViewer from '../components/MissionsManagerViewer';
import CamerasViewer from '../components/CamerasViewer';
import SensorData from '../components/SensorData';
import SystemStatus from '../components/SystemStatus';
import Widgets from '../components/Widgets';

const MISSION_THRESHOLD = 1; // meters

const panelOptions = [
  { value: '3d', label: '3D Model', component: BoatViewer },
  { value: 'gps', label: 'GPS', component: MapPanel },
  { value: 'radar', label: 'Radar', component: RadarViewer },
  { value: 'currentMission', label: 'Current Mission', component: CurrentMissionViewer },
  { value: 'missionsManager', label: 'Missions Manager', component: MissionsManagerViewer },
  { value: 'cameras', label: 'Onboard Cameras', component: CamerasViewer },
];

export default function MainScreen({ sensors }) {
  const [leftPanel, setLeftPanel] = useState('3d');
  const [rightPanel, setRightPanel] = useState('gps');
  const [missionsState, setMissionsState] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('missions') || '{}');
    } catch (e) {
      return {};
    }
  });
  const [mode, setMode] = useState('Manual');
  const [currentMission, setCurrentMission] = useState(null);
  const [currentWpIdx, setCurrentWpIdx] = useState(0);
  const [gpsTrail, setGpsTrail] = useState([]);
  const [selectedMission, setSelectedMission] = useState('');
  const prevGpsPos = useRef(null);

  const setMissions = (m) => {
    setMissionsState(m);
    localStorage.setItem('missions', JSON.stringify(m));
  };

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
            {panelOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <div className="panel">{renderPanel(leftPanel)}</div>
        </div>
        <div className="panel-container">
          <select value={rightPanel} onChange={(e) => setRightPanel(e.target.value)}>
            {panelOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <div className="panel">{renderPanel(rightPanel)}</div>
        </div>
      </div>
      <div className="bottom-panels">
        <SensorData sensors={sensorsWithMode} />
        <SystemStatus sensors={sensorsWithMode} />
        <Widgets sensors={sensorsWithMode} />
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
