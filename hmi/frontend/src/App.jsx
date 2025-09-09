import { Routes, Route } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import { useSimStore } from './state/simStore';
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

  // Simulation override: if any simulator is active, force connection to Simulation
  const { imuActive, gpsActive } = useSimStore((s) => ({ imuActive: s.imuActive, gpsActive: s.gpsActive }));
  const simActive = imuActive || gpsActive;

  // Baseline snapshots to restore after simulation stops
  const baselineImuRef = useRef(null);
  const baselineGpsRef = useRef(null);
  const baselineConnRef = useRef(null);
  const baselineLastImuRef = useRef(null);
  const baselineLastGpsRef = useRef(null);
  const prevImuActiveRef = useRef(false);
  const prevGpsActiveRef = useRef(false);
  const prevSimActiveRef = useRef(false);

  // On simulation toggle, capture baselines
  useEffect(() => {
    const prevImu = prevImuActiveRef.current;
    const prevGps = prevGpsActiveRef.current;
    const prevSim = prevSimActiveRef.current;

    // Simulation just started for IMU
    if (!prevImu && imuActive) {
      baselineImuRef.current = status.imu;
      baselineLastImuRef.current = status.lastImu;
    }
    // Simulation just started for GPS
    if (!prevGps && gpsActive) {
      baselineGpsRef.current = status.gps;
      baselineLastGpsRef.current = status.lastGps;
    }
    // Any simulation just started (overall)
    if (!prevSim && simActive) {
      if (status.imu === 'Not initialized' && status.gps === 'Not initialized') {
        baselineConnRef.current = 'Initializing';
      } else {
        baselineConnRef.current = status.connection;
      }
    }

    prevImuActiveRef.current = imuActive;
    prevGpsActiveRef.current = gpsActive;
    prevSimActiveRef.current = simActive;
  }, [imuActive, gpsActive, simActive, status.imu, status.gps, status.lastImu, status.lastGps, status.connection]);

  // Helper to decide if there has been new real sensor data since simulation start
  const isSameLast = (cur, base) => {
    if (cur == null && base == null) return true;
    if (cur == null || base == null) return false;
    return Number(cur) === Number(base);
  };

  // Compute sensor display state honoring baseline after simulation stops
  const imuSimulatedState = (() => {
    if (imuActive) return 'Simulated';
    // If not active and no new real sensor data since sim started, restore baseline
    if (isSameLast(status.lastImu, baselineLastImuRef.current) && baselineImuRef.current) {
      return baselineImuRef.current;
    }
    return status.imu;
  })();

  const gpsSimulatedState = (() => {
    if (gpsActive) return 'Simulated';
    if (isSameLast(status.lastGps, baselineLastGpsRef.current) && baselineGpsRef.current) {
      return baselineGpsRef.current;
    }
    return status.gps;
  })();

  useEffect(() => {
    const wsUrl = import.meta.env.VITE_BACKEND_WS || 'ws://localhost:8001/ws';
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      setData(msg);
      const now = msg.last_message_time;
      const sensorLast = msg.sensor_last || {};
      setStatus((prev) => {
        // Only count sensor/* messages for initialization and activity
        const lastImu = sensorLast.imu ?? null;
        const lastGps = sensorLast.gps ?? null;
        const nowSec = Date.now() / 1000;
        const ACTIVE_T = 10; // seconds to consider sensor active

        // IMU state with recency awareness
        const imuVals = [msg.sensors.roll, msg.sensors.pitch, msg.sensors.heading];
        const imuValid = imuVals.every((v) => v !== undefined && v !== null && Number.isFinite(v));
        let imu;
        if (Number.isFinite(lastImu)) {
          if (nowSec - Number(lastImu) > ACTIVE_T) {
            imu = 'Inactive';
          } else {
            imu = imuValid ? 'OK' : (prev.imu === 'Not initialized' ? 'Initializing' : 'Degraded');
          }
        } else {
          imu = 'Not initialized';
        }

        // GPS state with recency awareness
        const gpsVals = [msg.sensors.latitude, msg.sensors.longitude];
        const gpsValid = gpsVals.every((v) => v !== undefined && v !== null && Number.isFinite(v));
        let gps;
        if (Number.isFinite(lastGps)) {
          if (nowSec - Number(lastGps) > ACTIVE_T) {
            gps = 'Inactive';
          } else {
            gps = gpsValid ? 'OK' : (prev.gps === 'Not initialized' ? 'Initializing' : 'Degraded');
          }
        } else {
          gps = 'Not initialized';
        }

        // Connection state machine (explicit handling for both Not initialized)
        let connection;
        const allOk = imu === 'OK' && gps === 'OK';
        const bothNotInit = imu === 'Not initialized' && gps === 'Not initialized';
        if (bothNotInit) {
            connection = 'Initializing';
        } else if (prev.connection === 'Not initialized') {
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
          const bothNotInit = imu === 'Not initialized' && gps === 'Not initialized';
          if (bothNotInit) {
            connection = 'Initializing';
          } else if (prev.connection === 'Not initialized') {
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

  const lastMessage = status.lastMessage ? new Date(status.lastMessage * 1000) : null;

  // Effective connection: Simulation while active; when stopping, if no new real data since sim start, restore baseline connection
  const effectiveConnection = (() => {
    if (simActive) return 'Simulation';
    // If no new real sensor data has arrived since simulation started, use baseline connection
    const noNewImu = isSameLast(status.lastImu, baselineLastImuRef.current);
    const noNewGps = isSameLast(status.lastGps, baselineLastGpsRef.current);
    if (noNewImu && noNewGps && baselineConnRef.current) {
      return baselineConnRef.current;
    }
    return status.connection;
  })();
  const connClass =
    {
      OK: 'green',
      Inactive: 'red',
      Degraded: 'orange',
      Initializing: 'lightgreen',
      Simulation: 'blue',
      'Not initialized': 'yellow',
    }[effectiveConnection] || 'red';
  const connectionDisplay =
    effectiveConnection === 'Inactive' && lastMessage
      ? `Inactive (Last message: ${lastMessage.toLocaleTimeString()})`
      : effectiveConnection;

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
                imu_state: imuSimulatedState,
                gps_state: gpsSimulatedState,
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
