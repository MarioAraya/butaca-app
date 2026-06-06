function shortName(name) {
  const n = name.toLowerCase()
  if (n.includes('normandie')) return 'Normandie'
  if (n.includes('imperio')) return 'Imperio'
  if (n.includes('estaci')) return 'Arauco Est.'
  return name
}

export default function CinemaFilter({ cinemas, selected, onToggle }) {
  if (cinemas.length <= 1) return null

  return (
    <div class="cinema-filter-wrapper">
      <div class="cinema-filter" role="group" aria-label="Filtrar por cine">
        {cinemas.map((c) => (
          <button
            key={c}
            class={`cinema-tab${selected.has(c) ? ' active' : ''}`}
            aria-pressed={selected.has(c)}
            onClick={() => onToggle(c)}
          >
            {shortName(c)}
          </button>
        ))}
      </div>
    </div>
  )
}
