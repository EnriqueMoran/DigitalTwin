export default function SensorData({ sensors = {} }) {
  const fields = [
    ['Latitude', sensors.latitude],
    ['Longitude', sensors.longitude],
    ['Altitude', sensors.altitude],
    ['Heading', sensors.heading],
    ['Roll', sensors.roll],
    ['Pitch', sensors.pitch],
    ['Estimated speed', sensors.estimated_speed],
    ['Estimated speed confidence', sensors.estimated_speed_confidence],
    ['True speed', sensors.true_speed],
    ['Rate of turn', sensors.rate_of_turn],
  ];
  return (
    <div>
      <h3>Sensor Data</h3>
      <table>
        <tbody>
          {fields.map(([label, value]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{value !== undefined && value !== null ? value : 'Null'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
