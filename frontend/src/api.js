const BASE = import.meta.env.VITE_API_URL ?? ''

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const fetchMovies = () => get('/api/v1/movies')
export const fetchMovieDetail = (slug) => get(`/api/v1/movies/${slug}`)
