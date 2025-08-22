import { MapContainer, TileLayer, Marker } from 'react-leaflet';
import L from 'leaflet';

// The overhead boat icon should be placed at `hmi/frontend/public/boat_top.png`.
// This binary asset is not tracked and must be provided separately.
const boatIconUrl = '/boat_top.png';
import 'leaflet/dist/leaflet.css';

const boatIcon = L.icon({
  iconUrl: boatIconUrl,
  iconSize: [40, 40],
  iconAnchor: [20, 20],
});

export default function MapPanel({ sensors }) {
  const { latitude = 0, longitude = 0 } = sensors || {};
  const position = [latitude || 0, longitude || 0];

  return (
    <MapContainer center={position} zoom={13} style={{ height: '100%', width: '100%' }}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <Marker position={position} icon={boatIcon} />
    </MapContainer>
  );
}
