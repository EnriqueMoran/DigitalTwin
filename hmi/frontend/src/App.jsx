import { Link, Routes, Route } from 'react-router-dom';
import { useEffect, useState } from 'react';
import MainScreen from './screens/Main';
import MissionsScreen from './screens/Missions';
import CameraScreen from './screens/Camera';

function App() {
  const [data, setData] = useState({ sensors: {}, last_message_time: null });

  useEffect(() => {
    const wsUrl = import.meta.env.VITE_BACKEND_WS || 'ws://localhost:8001/ws';
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      setData(msg);
    };
    return () => ws.close();
  }, []);

  const lastMessage = data.last_message_time ? new Date(data.last_message_time * 1000) : null;
  const active = lastMessage && (Date.now() / 1000 - data.last_message_time < 5);

  return (
    <>
      <nav className="top-nav">
        <Link to="/">Main</Link>
        <Link to="/missions">Missions</Link>
        <Link to="/camera">Camera</Link>
        <span className="connection">
          <span className={`dot ${active ? 'green' : 'red'}`}></span>
          {active ? 'Active' : 'Inactive'}
          {!active && lastMessage && (
            <span className="last-message">Last message: {lastMessage.toLocaleString()}</span>
          )}
        </span>
      </nav>
      <Routes>
        <Route
          path="/"
          element={<MainScreen sensors={{ ...data.sensors, connection_state: active ? 'Active' : 'Inactive' }} />}
        />
        <Route path="/missions" element={<MissionsScreen />} />
        <Route path="/camera" element={<CameraScreen />} />
      </Routes>
    </>
  );
}

export default App;
