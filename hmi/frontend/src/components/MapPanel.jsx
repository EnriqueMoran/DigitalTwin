import { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// The overhead boat icon should be placed at `hmi/frontend/public/boat_top.png`.
// This binary asset is not tracked and must be provided separately.
const boatIconUrl = '/boat_top.png';

const boatIcon = L.icon({
  iconUrl: boatIconUrl,
  iconSize: [40, 40],
  iconAnchor: [20, 20],
});

export default function MapPanel({ sensors }) {
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const lastPos = useRef([0, 0]);

  useEffect(() => {
    if (!sensors) return;
    const { latitude = 0, longitude = 0 } = sensors;
    const pos = [latitude || 0, longitude || 0];
    lastPos.current = pos;
    if (markerRef.current) {
      markerRef.current.setLatLng(pos);
    }
  }, [sensors]);

  const handleCenter = () => {
    if (mapRef.current) {
      mapRef.current.setView(lastPos.current);
    }
  };

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
        <Marker position={[0, 0]} icon={boatIcon} ref={markerRef} />
      </MapContainer>
      <button
        style={{ position: 'absolute', top: 10, right: 10, zIndex: 1000 }}
        onClick={handleCenter}
      >
        Center
      </button>
    </div>
  );
}
