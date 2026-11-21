import { useEffect, useState } from 'preact/hooks'
import { fetchRoom } from '../api'

function SeatMap({ room }) {
  const cols = []
  for (let c = room.max_col; c >= room.min_col; c--) cols.push(c)
  const aisles = new Set(room.aisles_after)

  return (
    <div class="seatmap" style={{ '--cols': cols.length }}>
      <div class="seatmap-screen">Pantalla</div>
      {room.rows.map((row) => {
        const byCol = new Map(row.seats.map((s) => [s.col, s]))
        return (
          <div key={row.name} class={`seatmap-row${aisles.has(row.name) ? ' seatmap-row-aisle' : ''}`}>
            <span class="seatmap-label">{row.name}</span>
            {cols.map((c) => {
              const seat = byCol.get(c)
              return seat ? (
                <span
                  key={c}
                  class={`seatmap-seat${seat.style && seat.style !== 'Normal' ? ' seatmap-seat-special' : ''}`}
                  title={`Fila ${row.name}, butaca ${seat.id}`}
                >
                  {seat.id}
                </span>
              ) : (
                <span key={c} class="seatmap-gap" aria-hidden="true" />
              )
            })}
          </div>
        )
      })}
    </div>
  )
}

export default function RoomModal({ cinemaName, roomName, onClose }) {
  const [state, setState] = useState({ status: 'loading', room: null })

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading', room: null })
    fetchRoom(cinemaName, roomName)
      .then((room) => !cancelled && setState({ status: room ? 'ready' : 'missing', room }))
      .catch(() => !cancelled && setState({ status: 'error', room: null }))
    return () => {
      cancelled = true
    }
  }, [cinemaName, roomName])

  const { status, room } = state

  return (
    <div class="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div class="modal-sheet" onClick={(e) => e.stopPropagation()}>
        <div class="modal-handle" />
        <button class="modal-close" onClick={onClose} aria-label="Cerrar">✕</button>

        <div class="modal-content">
          <h2 class="modal-title">{roomName}</h2>
          <div class="modal-meta">
            <span class="modal-genres">{cinemaName}</span>
            {room && <span class="badge">{room.total_seats} butacas</span>}
            {room && <span class="badge">{room.rows.length} filas</span>}
            {room?.formats.map((f) => <span key={f} class="badge">{f}</span>)}
          </div>

          {status === 'loading' && <p class="seatmap-note">Cargando sala…</p>}
          {status === 'error' && <p class="seatmap-note">No se pudo cargar el mapa de la sala.</p>}
          {status === 'missing' && <p class="seatmap-note">Aún no hay mapa de esta sala.</p>}
          {status === 'ready' && (
            <>
              <SeatMap room={room} />
              <p class="seatmap-note">Distribución de la sala. No muestra butacas ocupadas.</p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
