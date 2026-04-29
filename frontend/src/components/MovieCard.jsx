function formatTime(t) {
  return String(t).slice(0, 5)
}

export default function MovieCard({ movie, byCinema }) {
  return (
    <article class="movie-card">
      <div class="movie-poster">
        {movie.poster_url ? (
          <img
            src={movie.poster_url}
            alt={movie.title}
            loading="lazy"
            decoding="async"
          />
        ) : (
          <div class="movie-poster-placeholder" aria-hidden="true">🎬</div>
        )}
      </div>

      <div class="movie-body">
        <h2 class="movie-title" title={movie.title}>
          {movie.title}
        </h2>

        <div class="movie-meta">
          {movie.age_rating && <span class="badge">{movie.age_rating}</span>}
          {movie.runtime_minutes && (
            <span class="badge">{movie.runtime_minutes} min</span>
          )}
        </div>

        {movie.genres && (
          <div class="movie-genres">{movie.genres}</div>
        )}

        {Object.entries(byCinema).map(([cinemaName, times]) => (
          <div key={cinemaName} class="cinema-section">
            <div class="cinema-label">{cinemaName}</div>
            <div class="showtimes-row">
              {times
                .slice()
                .sort((a, b) => String(a.show_time).localeCompare(String(b.show_time)))
                .map((t) => (
                  <span key={t.id} class="time-pill">
                    {formatTime(t.show_time)}
                    {t.format && (
                      <span class="time-pill-tag">{t.format}</span>
                    )}
                    {t.language && (
                      <span class="time-pill-tag">{t.language}</span>
                    )}
                  </span>
                ))}
            </div>
          </div>
        ))}
      </div>
    </article>
  )
}
