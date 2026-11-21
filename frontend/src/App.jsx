import { useState, useEffect, useCallback, useMemo } from 'preact/hooks'
import { fetchBillboard } from './api'
import Header from './components/Header'
import DateTabs from './components/DateTabs'
import CinemaFilter from './components/CinemaFilter'
import MovieCard from './components/MovieCard'
import MovieModal from './components/MovieModal'
import RoomModal from './components/RoomModal'

const TARGET_PATTERNS = ['imperio', 'estaci', 'normandie']

function isTargetCinema(name) {
  const lower = name.toLowerCase()
  return TARGET_PATTERNS.some((p) => lower.includes(p))
}

export default function App() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [movieData, setMovieData] = useState([])
  const [dates, setDates] = useState([])
  const [selectedDate, setSelectedDate] = useState(null)
  const [selectedCinemas, setSelectedCinemas] = useState(new Set())
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [selectedMovie, setSelectedMovie] = useState(null)
  const [selectedRoom, setSelectedRoom] = useState(null)
  const closeRoom = useCallback(() => setSelectedRoom(null), [])

  useEffect(() => {
    const onOnline = () => setIsOnline(true)
    const onOffline = () => setIsOnline(false)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const details = await fetchBillboard()

      const filtered = details
        .map((d) => ({
          ...d,
          showtimes: d.showtimes.filter((st) => isTargetCinema(st.cinema_name)),
        }))
        .filter((d) => d.showtimes.length > 0)

      const dateSet = new Set(filtered.flatMap((d) => d.showtimes.map((st) => st.show_date)))
      const sortedDates = [...dateSet].sort()

      const data = filtered.map((d) => {
        const byCinema = {}
        for (const st of d.showtimes) {
          if (!byCinema[st.cinema_name]) byCinema[st.cinema_name] = []
          byCinema[st.cinema_name].push(st)
        }
        return { movie: d, byCinema }
      })

      setMovieData(data)
      setDates(sortedDates)
      setSelectedDate((prev) =>
        prev && sortedDates.includes(prev) ? prev : (sortedDates[0] ?? null)
      )
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const allCinemas = useMemo(() => {
    const names = new Set(movieData.flatMap(({ byCinema }) => Object.keys(byCinema)))
    return [...names].sort()
  }, [movieData])

  function toggleCinema(name) {
    setSelectedCinemas((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const visibleMovies = selectedDate
    ? movieData
        .map(({ movie, byCinema }) => {
          const filteredByCinema = Object.fromEntries(
            Object.entries(byCinema)
              .map(([cinema, times]) => [
                cinema,
                times.filter((t) => t.show_date === selectedDate),
              ])
              .filter(([, times]) => times.length > 0)
              .filter(([cinema]) => selectedCinemas.size === 0 || selectedCinemas.has(cinema))
          )
          return { movie, byCinema: filteredByCinema }
        })
        .filter(({ byCinema }) => Object.keys(byCinema).length > 0)
    : []

  return (
    <div class="app">
      <Header loading={loading} onRefresh={loadData} />

      {!isOnline && (
        <div class="offline-banner" role="status">
          Sin conexión — mostrando datos guardados
        </div>
      )}

      <DateTabs dates={dates} selected={selectedDate} onSelect={setSelectedDate} />
      <CinemaFilter cinemas={allCinemas} selected={selectedCinemas} onToggle={toggleCinema} />

      <main class="movies-list">
        {loading ? (
          Array.from({ length: 6 }, (_, i) => (
            <div key={i} class="skeleton-card" aria-hidden="true" />
          ))
        ) : error ? (
          <div class="error-container" role="alert">
            <div class="error-title">Error al cargar la cartelera</div>
            <p>{error}</p>
            <button class="retry-btn" onClick={loadData}>
              Reintentar
            </button>
          </div>
        ) : visibleMovies.length === 0 ? (
          <div class="empty-state">
            <div class="empty-state-icon" aria-hidden="true">🎬</div>
            <p>No hay funciones para este día</p>
          </div>
        ) : (
          visibleMovies.map(({ movie, byCinema }) => (
            <MovieCard key={movie.id} movie={movie} byCinema={byCinema} onSelect={() => setSelectedMovie(movie)}
              onRoomSelect={(cinemaName, roomName) => setSelectedRoom({ cinemaName, roomName })} />
          ))
        )}
      </main>
      {selectedMovie && (
        <MovieModal movie={selectedMovie} onClose={() => setSelectedMovie(null)} />
      )}
      {selectedRoom && (
        <RoomModal cinemaName={selectedRoom.cinemaName} roomName={selectedRoom.roomName} onClose={closeRoom} />
      )}
    </div>
  )
}
