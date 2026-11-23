export default function MyAppointmentsPage({ items = [] }) {
  return items.length ? <ul>{items.map((a) => <li key={a.id}>{a.when}</li>)}</ul> : <p>Nothing here yet</p>;
}
