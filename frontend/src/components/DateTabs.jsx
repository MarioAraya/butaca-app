const DAYS_ES = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb']

function getTodayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function formatTab(dateStr) {
  const today = getTodayStr()
  const d = new Date()
  d.setDate(d.getDate() + 1)
  const tomorrow = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

  if (dateStr === today) return 'Hoy'
  if (dateStr === tomorrow) return 'Mañana'

  const [y, m, day] = dateStr.split('-').map(Number)
  const date = new Date(y, m - 1, day)
  return `${DAYS_ES[date.getDay()]} ${date.getDate()}`
}

export default function DateTabs({ dates, selected, onSelect }) {
  if (!dates.length) return null

  return (
    <div class="date-tabs-wrapper">
      <div class="date-tabs" role="tablist" aria-label="Seleccionar fecha">
        {dates.map((d) => (
          <button
            key={d}
            class={`date-tab${selected === d ? ' active' : ''}`}
            role="tab"
            aria-selected={selected === d}
            onClick={() => onSelect(d)}
          >
            {formatTab(d)}
          </button>
        ))}
      </div>
    </div>
  )
}
