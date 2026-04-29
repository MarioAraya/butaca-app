export default function Header({ loading, onRefresh }) {
  return (
    <header class="header">
      <h1 class="header-title">
        ¿Qué ver en <span>el cine</span> hoy?
      </h1>
      <button
        class={`refresh-btn${loading ? ' spinning' : ''}`}
        onClick={onRefresh}
        disabled={loading}
        aria-label="Actualizar cartelera"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
          <path d="M21 3v5h-5" />
          <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
          <path d="M8 16H3v5" />
        </svg>
      </button>
    </header>
  )
}
