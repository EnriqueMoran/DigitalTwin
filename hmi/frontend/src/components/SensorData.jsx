export default function SensorData({ sensors = {} }) {
  const toDeg = (r) => (r !== undefined && r !== null ? (r * 180) / Math.PI : null);
  const fmt = (v, unit = '', transform, decimals) => {
    if (v === undefined || v === null) return 'Null';
    let val = transform ? transform(v) : v;
    if (decimals !== undefined) val = parseFloat(Number(val).toFixed(decimals));
    return `${val}${unit}`;
  };

  const fields = [
    ['Latitude (deg)', fmt(sensors.latitude, '', null, 6)],
    ['Longitude (deg)', fmt(sensors.longitude, '', null, 6)],
    ['Altitude (m)', fmt(sensors.altitude, '', null, 2)],
    ['Heading (deg)', fmt(sensors.heading, '', toDeg, 0)],
    ['Roll (deg)', fmt(sensors.roll, '', toDeg, 2)],
    ['Pitch (deg)', fmt(sensors.pitch, '', toDeg, 2)],
    ['Estimated speed (m/s)', fmt(sensors.estimated_speed, '', null, 3)],
    ['E.S. Confidence', fmt(sensors.estimated_speed_confidence, '%')],
    ['True speed (m/s)', fmt(sensors.true_speed, '', null, 3)],
    ['Rate of turn (deg/s)', fmt(sensors.rate_of_turn, '', toDeg, 2)],
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
