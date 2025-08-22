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

  useEffect(() => {
    if (!sensors) return;
    const { latitude = 0, longitude = 0 } = sensors;
    const pos = [latitude || 0, longitude || 0];
    if (markerRef.current) {
      markerRef.current.setLatLng(pos);
    }
    if (mapRef.current) {
      mapRef.current.setView(pos);
    }
  }, [sensors]);

  return (
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
  );
}
