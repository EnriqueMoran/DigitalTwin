export default function SensorData({ sensors = {} }) {
  const toDeg = (r) =>
    r !== undefined && r !== null ? ((r * 180) / Math.PI).toFixed(2) : null;

  const toFixed = (digits) => (v) => Number(v).toFixed(digits);

  const toDMS = (deg) => {
    const absolute = Math.abs(deg);
    const d = Math.floor(absolute);
    const mFloat = (absolute - d) * 60;
    const m = Math.floor(mFloat);
    const s = ((mFloat - m) * 60).toFixed(2);
    const sign = deg < 0 ? '-' : '';
    return `${sign}${d}° ${m}' ${s}"`;
  };

  const fmt = (v, unit = '', transform) => {
    if (v === undefined || v === null) return 'Null';
    const val = transform ? transform(v) : v;
    return `${val}${unit}`;
  };

  const fmtLatLon = (v) => {
    if (v === undefined || v === null) return 'Null';
    const dec = Number(v).toFixed(5);
    return `${dec} (${toDMS(v)})`;
  };

  const fields = [
    ['Latitude', fmtLatLon(sensors.latitude)],
    ['Longitude', fmtLatLon(sensors.longitude)],
    ['Altitude (m)', fmt(sensors.altitude, '', toFixed(2))],
    ['Heading (deg)', fmt(sensors.heading, '', toDeg)],
    ['Roll (deg)', fmt(sensors.roll, '', toDeg)],
    ['Pitch (deg)', fmt(sensors.pitch, '', toDeg)],
    ['Estimated speed (m/s)', fmt(sensors.estimated_speed, '', toFixed(3))],
    ['E.S. Confidence', fmt(sensors.estimated_speed_confidence, '%')],
    ['True speed (m/s)', fmt(sensors.true_speed, '', toFixed(3))],
    ['Rate of turn (deg/s)', fmt(sensors.rate_of_turn, '', toDeg)],
  ];
  return (
    <div>
      <h3>Sensor Data</h3>
      <table>
        <tbody>
          {fields.map(([label, value]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
