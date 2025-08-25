import { useState } from 'react';
import BoatViewer from '../components/BoatViewer';
import MapPanel from '../components/MapPanel';
import RadarViewer from '../components/RadarViewer';
import CurrentMissionViewer from '../components/CurrentMissionViewer';
import MissionsManagerViewer from '../components/MissionsManagerViewer';
import CamerasViewer from '../components/CamerasViewer';
import SensorData from '../components/SensorData';
import SystemStatus from '../components/SystemStatus';
import Widgets from '../components/Widgets';

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

  const renderPanel = (value) => {
    const opt = panelOptions.find((o) => o.value === value);
    if (!opt) return null;
    const Comp = opt.component;
    return <Comp sensors={sensors} />;
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
        <SensorData sensors={sensors} />
        <SystemStatus sensors={sensors} />
        <Widgets sensors={sensors} />
      </div>
    </div>
  );
}
