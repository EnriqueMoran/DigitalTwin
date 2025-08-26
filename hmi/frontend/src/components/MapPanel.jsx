import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const boatIconUrl = '/boat_top.png';

const createBoatIcon = (angle = 0) => {
  return L.divIcon({
    html: `<img src="${boatIconUrl}" style="transform: rotate(${angle}deg); width:40px; height:40px;"/>`,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    className: '',
  });
};

const createMissionIcon = (num, active) => {
  const cls = active ? 'mission-icon active' : 'mission-icon';
  return L.divIcon({
    html: `<div class="${cls}">${num}</div>`,
    className: '',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
};

function MapReadyListener({ onReady }) {
  const map = useMap();
  useEffect(() => {
    if (map && typeof onReady === 'function') onReady(map);
  }, [map, onReady]);
  return null;
}

export default function MapPanel({
  sensors,
  missions = {},
  selectedMission = '',
  currentMission,
  currentWpIdx = 0,
  trail = [],
}) {
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const pendingCenterRef = useRef(false);
  const lastHeading = useRef(null);
  const lastPanRef = useRef(0);

  const sensorsRef = useRef(sensors);
  const followRef = useRef(true);

  const [follow, setFollow] = useState(true);
  const [position, setPosition] = useState(null);
  const [showMission, setShowMission] = useState(false);
  const [contextMenu, setContextMenu] = useState(null);

  useEffect(() => { sensorsRef.current = sensors; }, [sensors]);
  useEffect(() => { followRef.current = follow; }, [follow]);
  useEffect(() => setShowMission(false), [selectedMission]);

  const PAN_MIN_MS = 125;

  const headingDeg = useMemo(() => {
    const heading = sensors?.heading;
    if (heading == null) return null;
    const h = Number(heading);
    if (!Number.isFinite(h)) return null;
    const deg = Math.abs(h) > 2 * Math.PI ? h : (h * 180) / Math.PI;
    return ((deg % 360) + 360) % 360; // normalize to [0,360)
  }, [sensors?.heading]);

  const memoIcon = useMemo(() => createBoatIcon(headingDeg ?? 0), [headingDeg]);

  useEffect(() => {
    if (!sensors) return;
    const latRaw = sensors.latitude ?? sensors.lat ?? sensors.y ?? sensors.gps_latitude ?? null;
    const lonRaw =
      sensors.longitude ??
      sensors.lon ??
      sensors.lng ??
      sensors.long ??
      sensors.gps_longitude ??
      null;
    const lat = latRaw == null ? NaN : Number(latRaw);
    const lon = lonRaw == null ? NaN : Number(lonRaw);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || (lat === 0 && lon === 0)) return;

    const pos = [lat, lon];
    setPosition(pos);

    const map = mapRef.current;
    if (map && followRef.current) {
      const now = Date.now();
      if (now - lastPanRef.current >= PAN_MIN_MS) {
        map.panTo(pos);
        lastPanRef.current = now;
      }
    }

  }, [sensors]);

  useEffect(() => {
    if (markerRef.current) {
      // Avoid tiny micro-updates if value didn't meaningfully change.
      if (lastHeading.current == null || Math.abs((headingDeg ?? 0) - lastHeading.current) > 0.1) {
        try {
          markerRef.current.setIcon(createBoatIcon(headingDeg ?? 0));
          lastHeading.current = headingDeg ?? 0;
        } catch (err) {
          console.error('[MapPanel] failed to update marker icon', err);
        }
      }
    }
  }, [headingDeg]);

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

    mapInstance.on('contextmenu', (e) => {
      e.originalEvent.preventDefault();
      setContextMenu({
        lat: e.latlng.lat,
        lon: e.latlng.lng,
        x: e.containerPoint.x,
        y: e.containerPoint.y,
      });
    });

    mapInstance.on('click', () => setContextMenu(null));
    mapInstance.on('movestart', () => setContextMenu(null));
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

  const handleCopyCoords = () => {
    if (!contextMenu) return;
    const text = `${contextMenu.lat.toFixed(15)}, ${contextMenu.lon.toFixed(15)}`;
    navigator.clipboard?.writeText(text);
    setContextMenu(null);
  };

  const missionWps = selectedMission ? missions[selectedMission] || [] : [];
  const activeIdx =
    currentMission === selectedMission ? currentWpIdx : 0;

  const missionMarkers = showMission
    ? missionWps.map((wp, idx) => (
        <Marker
          key={`m${idx}`}
          position={[Number(wp.lat), Number(wp.lon)]}
          icon={createMissionIcon(idx + 1, idx === activeIdx)}
        />
      ))
    : null;

  return (
    <div style={{ height: '100%', width: '100%', position: 'relative' }}>
      <MapContainer center={[0, 0]} zoom={13} style={{ height: '100%', width: '100%' }}>
        <MapReadyListener onReady={handleMapReady} />
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Polyline positions={trail} pathOptions={{ color: 'yellow', dashArray: '4 4' }} />
        {missionMarkers}
        {position && <Marker position={position} icon={memoIcon} ref={markerRef} />}
      </MapContainer>

      <div style={{ position: 'absolute', bottom: 10, left: 10, zIndex: 1000, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <button onClick={handleCenter}>Center</button>
        <button onClick={handleFollow} disabled={follow}>
          {follow ? 'Following' : 'Follow'}
        </button>
        <button onClick={() => setShowMission((s) => !s)} disabled={!selectedMission}>
          Mission points
        </button>
      </div>
      {contextMenu && (
        <div
          className="context-menu"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          onClick={handleCopyCoords}
        >
          {contextMenu.lat.toFixed(6)}, {contextMenu.lon.toFixed(6)}
        </div>
      )}
    </div>
  );
}
