import { Routes, Route } from 'react-router-dom';
import { useEffect, useState } from 'react';
import MainScreen from './screens/Main';

function App() {
  const [data, setData] = useState({ sensors: {}, last_message_time: null });
  const [status, setStatus] = useState({
    connection: 'Not initialized',
    imu: 'Not initialized',
    gps: 'Not initialized',
    lastMessage: null,
    lastImu: null,
    lastGps: null,
  });

  useEffect(() => {
    const wsUrl = import.meta.env.VITE_BACKEND_WS || 'ws://localhost:8001/ws';
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      setData(msg);
      const now = msg.last_message_time;
      setStatus((prev) => {
        let imu = prev.imu;
        let gps = prev.gps;
        let lastImu = prev.lastImu;
        let lastGps = prev.lastGps;

        const imuVals = [msg.sensors.roll, msg.sensors.pitch, msg.sensors.heading];
        const imuHas = imuVals.some((v) => v !== undefined && v !== null);
        const imuValid = imuVals.every((v) => v !== undefined && v !== null && Number.isFinite(v));
        if (imuHas) {
          if (prev.imu === 'Not initialized') imu = imuValid ? 'OK' : 'Initializing';
          else imu = imuValid ? 'OK' : 'Degraded';
          if (imuValid) lastImu = now;
        }

        const gpsVals = [msg.sensors.latitude, msg.sensors.longitude];
        const gpsHas = gpsVals.some((v) => v !== undefined && v !== null);
        const gpsValid = gpsVals.every((v) => v !== undefined && v !== null && Number.isFinite(v));
        if (gpsHas) {
          if (prev.gps === 'Not initialized') gps = gpsValid ? 'OK' : 'Initializing';
          else gps = gpsValid ? 'OK' : 'Degraded';
          if (gpsValid) lastGps = now;
        }

        // Connection state machine
        let connection = prev.connection;
        const allOk = imu === 'OK' && gps === 'OK';
        if (prev.connection === 'Not initialized') {
          connection = 'Initializing';
        } else if (prev.connection === 'Initializing') {
          connection = allOk ? 'OK' : 'Initializing';
        } else if (prev.connection === 'Inactive') {
          connection = allOk ? 'OK' : 'Degraded';
        } else {
          connection = allOk ? 'OK' : 'Degraded';
        }

        return { connection, imu, gps, lastMessage: now, lastImu, lastGps };
      });
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      setStatus((prev) => {
        const now = Date.now() / 1000;
        let { connection, imu, gps, lastMessage, lastImu, lastGps } = prev;
        if (lastMessage && now - lastMessage > 10) connection = 'Inactive';
        if (lastImu && now - lastImu > 10) imu = 'Inactive';
        if (lastGps && now - lastGps > 10) gps = 'Inactive';
        if (connection !== 'Inactive') {
          const allOk = imu === 'OK' && gps === 'OK';
          if (prev.connection === 'Not initialized') {
            // No messages yet; remain Not initialized until first message arrives
            connection = 'Not initialized';
          } else if (prev.connection === 'Initializing') {
            connection = allOk ? 'OK' : 'Initializing';
          } else {
            connection = allOk ? 'OK' : 'Degraded';
          }
        }
        return { connection, imu, gps, lastMessage, lastImu, lastGps };
      });
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const lastMessage = status.lastMessage
    ? new Date(status.lastMessage * 1000)
    : null;
  const connClass =
    {
      OK: 'green',
      Inactive: 'red',
      Degraded: 'orange',
      Initializing: 'lightgreen',
      'Not initialized': 'yellow',
    }[status.connection] || 'red';
  const connectionDisplay =
    status.connection === 'Inactive' && lastMessage
      ? `Inactive (Last message: ${lastMessage.toLocaleTimeString()})`
      : status.connection;

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
                connection_state: status.connection,
                imu_state: status.imu,
                gps_state: status.gps,
                last_message_time: status.lastMessage,
              }}
            />
          }
        />
      </Routes>
    </>
  );
}

export default App;
