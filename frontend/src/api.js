const BASE = import.meta.env.VITE_API_URL ?? ''

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const fetchMovies = () => get('/api/v1/movies')
export const fetchMovieDetail = (slug) => get(`/api/v1/movies/${slug}`)
export const fetchBillboard = () => get('/api/v1/billboard')
export const fetchRoom = async (cinemaName, roomName) => {
  const qs = new URLSearchParams({ cinema_name: cinemaName, room_name: roomName })
  const rooms = await get(`/api/v1/rooms?${qs}`)
  return rooms[0] ?? null
}
