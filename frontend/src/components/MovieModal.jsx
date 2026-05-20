import { useEffect } from 'preact/hooks'

function getYoutubeEmbedUrl(url) {
  if (!url) return null
  const m = url.match(/(?:v=|youtu\.be\/)([A-Za-z0-9_-]{11})/)
  return m ? `https://www.youtube.com/embed/${m[1]}` : null
}

export default function MovieModal({ movie, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  const embedUrl = getYoutubeEmbedUrl(movie.trailer_url)

  return (
    <div class="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div class="modal-sheet" onClick={(e) => e.stopPropagation()}>
        <div class="modal-handle" />
        <button class="modal-close" onClick={onClose} aria-label="Cerrar">✕</button>

        <div class="modal-content">
          <h2 class="modal-title">{movie.title}</h2>

          <div class="modal-meta">
            {movie.age_rating && <span class="badge">{movie.age_rating}</span>}
            {movie.runtime_minutes && <span class="badge">{movie.runtime_minutes} min</span>}
            {movie.genres && <span class="modal-genres">{movie.genres}</span>}
          </div>

          {embedUrl && (
            <div class="modal-trailer">
              <iframe
                src={embedUrl}
                title={`Trailer ${movie.title}`}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              />
            </div>
          )}

          {movie.synopsis && (
            <div class="modal-synopsis">
              <div class="modal-synopsis-label">Sinopsis</div>
              <p>{movie.synopsis}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
