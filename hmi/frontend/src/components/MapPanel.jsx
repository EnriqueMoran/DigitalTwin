import { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, Marker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// The overhead boat icon should be placed at `hmi/frontend/public/boat_top.png`.
// This binary asset is not tracked and must be provided separately.
const boatIconUrl = '/boat_top.png';

const createBoatIcon = (angle = 0) =>
  L.divIcon({
    html: `<img src="${boatIconUrl}" style="transform: rotate(${angle}deg); width:40px; height:40px;"/>`,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    className: '',
  });

export default function MapPanel({ sensors }) {
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const initialCentered = useRef(false);
  const lastHeading = useRef(null);
  const [live, setLive] = useState(false);

  useEffect(() => {
    if (!sensors) return;
    const { latitude = 0, longitude = 0, heading } = sensors;
    const pos = [latitude || 0, longitude || 0];
    if (markerRef.current) {
      markerRef.current.setLatLng(pos);
    }
    if (live && mapRef.current) {
      mapRef.current.setView(pos);
    }

    if (heading !== undefined && markerRef.current) {
      const deg = (heading * 180) / Math.PI;
      const rounded = Math.round(deg / 5) * 5;
      if (lastHeading.current !== rounded) {
        markerRef.current.setIcon(createBoatIcon(rounded));
        lastHeading.current = rounded;
      }
    }

    if (!initialCentered.current && mapRef.current && sensors.latitude !== undefined && sensors.longitude !== undefined) {
      mapRef.current.setView(pos);
      initialCentered.current = true;
    }
  }, [sensors, live]);

  const handleCenter = () => {
    if (mapRef.current) {
      const { latitude = 0, longitude = 0 } = sensors || {};
      mapRef.current.setView([latitude || 0, longitude || 0]);
    }
  };

  const handleLive = () => {
    setLive(true);
    handleCenter();
  };

  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;
    const stopLive = () => setLive(false);
    map.on('dragstart', stopLive);
    map.on('zoomstart', stopLive);
    return () => {
      map.off('dragstart', stopLive);
      map.off('zoomstart', stopLive);
    };
  }, []);

  return (
    <div style={{ height: '100%', width: '100%', position: 'relative' }}>
      <MapContainer
        center={[0, 0]}
        zoom={13}
        style={{ height: '100%', width: '100%' }}
        whenCreated={(map) => {
          mapRef.current = map;
        }}
      >
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Marker position={[0, 0]} icon={createBoatIcon()} ref={markerRef} />
      </MapContainer>
      <div
        style={{ position: 'absolute', bottom: 10, left: 10, zIndex: 1000, display: 'flex', flexDirection: 'column', gap: 4 }}
      >
        <button onClick={handleCenter}>Center</button>
        <button onClick={handleLive}>Live</button>
      </div>
    </div>
  );
}
