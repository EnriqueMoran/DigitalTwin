import BoatViewer from '../components/BoatViewer';
import MapPanel from '../components/MapPanel';
import SensorData from '../components/SensorData';
import SystemStatus from '../components/SystemStatus';
import Widgets from '../components/Widgets';

export default function MainScreen({ sensors }) {
  return (
    <div className="main-screen">
      <div className="top-panels">
        <div className="panel"><BoatViewer sensors={sensors} /></div>
        <div className="panel"><MapPanel sensors={sensors} /></div>
      </div>
      <div className="bottom-panels">
        <SensorData sensors={sensors} />
        <SystemStatus sensors={sensors} />
        <Widgets sensors={sensors} />
      </div>
    </div>
  );
}
