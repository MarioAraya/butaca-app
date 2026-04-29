import { useState, useEffect, useCallback } from 'preact/hooks'
import { fetchMovies, fetchMovieDetail } from './api'
import Header from './components/Header'
import DateTabs from './components/DateTabs'
import MovieCard from './components/MovieCard'

const TARGET_PATTERNS = ['imperio', 'estaci']

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
  const [isOnline, setIsOnline] = useState(navigator.onLine)

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
      const movies = await fetchMovies()
      const details = await Promise.all(movies.map((m) => fetchMovieDetail(m.slug)))

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
            <MovieCard key={movie.id} movie={movie} byCinema={byCinema} />
          ))
        )}
      </main>
    </div>
  )
}
