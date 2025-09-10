import { Routes, Route } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import { useSimStore } from './state/simStore';
import MainScreen from './screens/Main';

function App() {
  const [data, setData] = useState({ sensors: {}, last_message_time: null, sensor_last: {}, sensor_states: {}, system_state: 'Initializing' });
  const [status, setStatus] = useState({
    connection: 'Initializing',
    imu: 'Not initialized',
    gps: 'Not initialized',
    lastMessage: null,
    lastImu: null,
    lastGps: null,
  });

  // Simulation override: if any simulator is active, force connection to Simulation
  const { imuActive, gpsActive } = useSimStore((s) => ({ imuActive: s.imuActive, gpsActive: s.gpsActive }));
  const simActive = imuActive || gpsActive;

  // We now rely on backend for state machine; HMI still tracks last timestamps to show recency
  const prevImuActiveRef = useRef(false);
  const prevGpsActiveRef = useRef(false);
  useEffect(() => {
    prevImuActiveRef.current = imuActive;
    prevGpsActiveRef.current = gpsActive;
  }, [imuActive, gpsActive]);

  useEffect(() => {
    const wsUrl = import.meta.env.VITE_BACKEND_WS || 'ws://localhost:8001/ws';
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      setData(msg);
      const now = msg.last_message_time;
      const sensorLast = msg.sensor_last || {};
      const sensorStates = msg.sensor_states || {};
      const systemState = msg.system_state || 'Initializing';
      setStatus(() => {
        const lastImu = sensorLast.imu ?? null;
        const lastGps = sensorLast.gps ?? null;
        const imu = sensorStates.imu || 'Not initialized';
        const gps = sensorStates.gps || 'Not initialized';
        const connection = systemState;
        return { connection, imu, gps, lastMessage: now, lastImu, lastGps };
      });
    };
    return () => ws.close();
  }, []);

  // Keep a lightweight recency updater for display (no state transitions — backend owns that)
  useEffect(() => {
    const id = setInterval(() => {
      setStatus((prev) => ({ ...prev }));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const lastMessage = status.lastMessage ? new Date(status.lastMessage * 1000) : null;

  // Effective connection comes from backend system_state
  const effectiveConnection = status.connection;
  const connClass =
    {
      OK: 'green',
      Unavailable: 'red',
      Degraded: 'orange',
      Initializing: 'lightgreen',
      Simulation: 'blue',
      'Not initialized': 'yellow',
    }[effectiveConnection] || 'red';
  let connectionDisplay = effectiveConnection;
  if (effectiveConnection === 'Unavailable') {
    const lastEsp = Math.max(Number(status.lastImu || 0), Number(status.lastGps || 0));
    if (lastEsp > 0) {
      const t = new Date(lastEsp * 1000).toLocaleTimeString();
      connectionDisplay = `Unavailable (Last message: ${t})`;
    }
  }

  return (
    <>
      <nav className="top-nav">
        <span className="connection">
          <span className={`dot ${connClass}`}></span>
          {connectionDisplay}
        </span>
      </nav>
      <Routes>
        <Route
          path="/"
          element={
            <MainScreen
              sensors={{
                ...data.sensors,
                connection_state: effectiveConnection,
                imu_state: status.imu,
                gps_state: status.gps,
                last_message_time: status.lastMessage,
                last_imu_time: status.lastImu,
                last_gps_time: status.lastGps,
              }}
            />
          }
        />
      </Routes>
    </>
  );
}

export default App;
