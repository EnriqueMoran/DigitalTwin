import { useCallback, useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const boatIconUrl = '/boat_top.png';
const createBoatIcon = (angle = 0) =>
  L.divIcon({
    html: `<img src="${boatIconUrl}" style="transform: rotate(${angle}deg); width:40px; height:40px;"/>`,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    className: '',
  });

function MapReadyListener({ onReady }) {
  const map = useMap();
  useEffect(() => {
    if (map && typeof onReady === 'function') onReady(map);
  }, [map, onReady]);
  return null;
}

export default function MapPanel({ sensors }) {
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const pendingCenterRef = useRef(false);
  const lastHeading = useRef(null);
  const lastPanRef = useRef(0);

  const sensorsRef = useRef(sensors);
  const followRef = useRef(true);

  const [follow, setFollow] = useState(true);

  useEffect(() => { sensorsRef.current = sensors; }, [sensors]);
  useEffect(() => { followRef.current = follow; }, [follow]);

  const PAN_MIN_MS = 125;

  useEffect(() => {
    if (!sensors) return;
    const latRaw = sensors.latitude ?? sensors.lat ?? sensors.y ?? 0;
    const lonRaw = sensors.longitude ?? sensors.lon ?? sensors.lng ?? sensors.long ?? 0;
    const lat = Number(latRaw);
    const lon = Number(lonRaw);
    const pos = [Number.isFinite(lat) ? lat : 0, Number.isFinite(lon) ? lon : 0];

    if (markerRef.current && typeof markerRef.current.setLatLng === 'function') {
      markerRef.current.setLatLng(pos);
    }

    const map = mapRef.current;
    if (map && followRef.current && Number.isFinite(lat) && Number.isFinite(lon)) {
      const now = Date.now();
      if (now - lastPanRef.current >= PAN_MIN_MS) {
        map.panTo(pos);
        lastPanRef.current = now;
      }
    }

    if (sensors.heading !== undefined && markerRef.current) {
      const deg = (sensors.heading * 180) / Math.PI;
      const rounded = Math.round(deg);
      if (lastHeading.current !== rounded) {
        markerRef.current.setIcon(createBoatIcon(rounded));
        lastHeading.current = rounded;
      }
    }
  }, [sensors]);

  const handleMapReady = useCallback((mapInstance) => {
    mapRef.current = mapInstance;

    if (pendingCenterRef.current) {
      pendingCenterRef.current = false;
      const latRaw = sensorsRef.current?.latitude ?? sensorsRef.current?.lat ?? null;
      const lonRaw = sensorsRef.current?.longitude ?? sensorsRef.current?.lon ?? null;
      const lat = latRaw == null ? NaN : Number(latRaw);
      const lon = lonRaw == null ? NaN : Number(lonRaw);
      if (Number.isFinite(lat) && Number.isFinite(lon)) {
        mapInstance.setView([lat, lon], mapInstance.getZoom());
      } else {
        console.warn('[MapPanel] pending center had invalid coords', { latRaw, lonRaw });
      }
    }

    const stopFollow = () => {
      if (followRef.current) {
        setFollow(false);
        followRef.current = false;
      }
    };

    mapInstance.off('dragstart', stopFollow);
    mapInstance.on('dragstart', stopFollow);
  }, []);

  useEffect(() => {
    return () => {
      const map = mapRef.current;
      if (map) {
        map.off('dragstart');
      }
    };
  }, []);

  const handleCenter = () => {
    const latRaw = sensorsRef.current?.latitude ?? sensorsRef.current?.lat ?? sensorsRef.current?.y ?? null;
    const lonRaw = sensorsRef.current?.longitude ?? sensorsRef.current?.lon ?? sensorsRef.current?.lng ?? sensorsRef.current?.long ?? null;
    const lat = latRaw == null ? NaN : Number(latRaw);
    const lon = lonRaw == null ? NaN : Number(lonRaw);

    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      pendingCenterRef.current = true;
      return;
    }

    const map = mapRef.current;
    if (!map) {
      pendingCenterRef.current = true;
      return;
    }

    try {
      map.flyTo([lat, lon], map.getZoom(), { animate: true, duration: 0.6 });
    } catch (err) {
      console.error('[MapPanel] flyTo failed, using setView', err);
      map.setView([lat, lon], map.getZoom());
    }
  };

  const handleFollow = () => {
    setFollow(true);
    followRef.current = true;
    handleCenter();
  };

  return (
    <div style={{ height: '100%', width: '100%', position: 'relative' }}>
      <MapContainer center={[0, 0]} zoom={13} style={{ height: '100%', width: '100%' }}>
        <MapReadyListener onReady={handleMapReady} />
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Marker position={[0, 0]} icon={createBoatIcon()} ref={markerRef} />
      </MapContainer>

      <div style={{ position: 'absolute', bottom: 10, left: 10, zIndex: 1000, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <button onClick={handleCenter}>Center</button>
        <button onClick={handleFollow} disabled={follow}>
          {follow ? 'Following' : 'Follow'}
        </button>
      </div>
    </div>
  );
}
