export default function BookAppointmentScreen({ slots = [] }) {
  return slots.length ? <ul>{slots.map((s) => <li key={s}>{s}</li>)}</ul> : <p>No free slots on this day</p>;
}
