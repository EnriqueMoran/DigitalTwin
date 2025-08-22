export default function SensorData({ sensors = {} }) {
  const toDeg = (r) => (r !== undefined && r !== null ? (r * 180 / Math.PI).toFixed(2) : null);
  const fmt = (v, unit = '', transform) => {
    if (v === undefined || v === null) return 'Null';
    const val = transform ? transform(v) : v;
    return `${val}${unit}`;
  };

  const fields = [
    ['Latitude (deg)', fmt(sensors.latitude)],
    ['Longitude (deg)', fmt(sensors.longitude)],
    ['Altitude (m)', fmt(sensors.altitude)],
    ['Heading (deg)', fmt(sensors.heading, '', toDeg)],
    ['Roll (deg)', fmt(sensors.roll, '', toDeg)],
    ['Pitch (deg)', fmt(sensors.pitch, '', toDeg)],
    ['Estimated speed (m/s)', fmt(sensors.estimated_speed)],
    ['E.S. Confidence', fmt(sensors.estimated_speed_confidence, '%')],
    ['True speed (m/s)', fmt(sensors.true_speed)],
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
