import type { Progreso } from "../../compartido/api/tipos";

type Tarea = Progreso["tareas_abiertas"][number];

const celda = (valor: unknown) => (valor === null || valor === undefined ? "—" : String(valor));

// Las cinco columnas tal como las manda el servidor, sin juntar ni traducir roles.
export function TareasAbiertas({ tareas }: { tareas: Tarea[] }) {
  if (tareas.length === 0) return <p className="avance__vacio">Sin tareas abiertas ahora mismo.</p>;
  return (
    <div className="tabla-envoltorio">
      <table className="tareas">
        <thead>
          <tr>
            <th scope="col">Rol</th>
            <th scope="col">Tarea</th>
            <th scope="col">Capítulo</th>
            <th scope="col">Escena</th>
            <th scope="col">Tokens de entrada</th>
          </tr>
        </thead>
        <tbody>
          {tareas.map((tarea, i) => (
            <tr key={i}>
              <td>{celda(tarea.rol)}</td>
              <td>{celda(tarea.tarea)}</td>
              <td>{celda(tarea.capitulo)}</td>
              <td>{celda(tarea.escena)}</td>
              <td className="numero">{celda(tarea.tokens)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
