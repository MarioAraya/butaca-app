"""Generator for Cinépolis rooms and seats HTML visualizer (docs/SALAS_CINEPOLIS.html)."""

from __future__ import annotations

import html
import re
from pathlib import Path


# Usable width of a room card (1100px container minus paddings), row labels and gaps
_MAP_WIDTH = 1040
_LABELS_WIDTH = 48
_GAP = 6


def _seat_size(n_cols: int) -> int:
    """Seat cell size in px so the widest row fits the card without horizontal scroll."""
    if n_cols <= 0:
        return 28
    fit = (_MAP_WIDTH - _LABELS_WIDTH - (n_cols + 1) * _GAP) // n_cols
    return max(14, min(28, fit))


def generate_rooms_html(rooms_data: list[dict], output_path: str = "docs/SALAS_CINEPOLIS.html") -> str:
    """Generate a clean dark-themed HTML visualization of cinemas, rooms, and seat layouts."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Group rooms by cinema
    by_cinema: dict[str, list[dict]] = {}
    for r in rooms_data:
        by_cinema.setdefault(r["cinema_name"], []).append(r)

    # Sort rooms within each cinema by room_name (e.g. Sala 1, Sala 2...)
    def room_sort_key(rm: dict):
        name = rm.get("room_name", "")
        # Try extracting integer if present
        match = re.search(r"\d+", name)
        return (int(match.group(0)) if match else 999, name)

    for cname in by_cinema:
        by_cinema[cname].sort(key=room_sort_key)

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Butaca — Mapa de Salas y Butacas Cinépolis</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  :root {{
    color-scheme: dark;
    --bg: #0d1117;
    --card-bg: #161b22;
    --card-border: #30363d;
    --text: #e6edf3;
    --text-muted: #8b949e;
    --accent: #58a6ff;
    --seat-available: #388bfd;
    --seat-sold: #484f58;
    --screen-bg: #21262d;
    --screen-border: #8b949e;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px 16px 60px;
    line-height: 1.5;
  }}
  .container {{
    max-width: 1100px;
    margin: 0 auto;
  }}
  header {{
    border-bottom: 2px solid var(--card-border);
    padding-bottom: 16px;
    margin-bottom: 24px;
  }}
  h1 {{
    font-size: 26px;
    font-weight: 700;
    margin-bottom: 8px;
    color: var(--text);
  }}
  p.subtitle {{
    color: var(--text-muted);
    font-size: 14px;
  }}
  .cinema-tabs {{
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
    border-bottom: 1px solid var(--card-border);
    padding-bottom: 12px;
    flex-wrap: wrap;
  }}
  .tab-btn {{
    background: #21262d;
    color: var(--text);
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
  }}
  .tab-btn:hover {{
    border-color: var(--accent);
  }}
  .tab-btn.active {{
    background: var(--accent);
    color: #ffffff;
    border-color: var(--accent);
  }}
  .room-chips {{
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
    overflow-x: auto;
    padding-bottom: 4px;
  }}
  .room-chip {{
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    color: var(--text-muted);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 13px;
    cursor: pointer;
    white-space: nowrap;
    text-decoration: none;
    transition: all 0.2s ease;
  }}
  .room-chip:hover, .room-chip.active {{
    color: var(--text);
    border-color: var(--accent);
  }}
  .room-card {{
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 36px;
    scroll-margin-top: 20px;
  }}
  .room-header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 20px;
    border-bottom: 1px solid var(--card-border);
    padding-bottom: 16px;
  }}
  .room-title {{
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .badge {{
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 12px;
    background: #1f6feb26;
    color: var(--accent);
    border: 1px solid #388bfd40;
    font-weight: normal;
  }}
  .room-meta {{
    font-size: 13px;
    color: var(--text-muted);
  }}
  .seat-type-preview {{
    display: flex;
    align-items: center;
    gap: 12px;
    background: #0d111780;
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 24px;
    font-size: 13px;
  }}
  .seat-type-icon {{
    width: 28px;
    height: 28px;
    flex-shrink: 0;
  }}
  .screen-bar {{
    background: var(--screen-bg);
    border: 1.5px solid var(--screen-border);
    border-radius: 8px;
    text-align: center;
    padding: 8px;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 1.5px;
    color: #e6edf3;
    margin: 0 auto 32px;
    max-width: 680px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  }}
  .legend {{
    display: flex;
    justify-content: center;
    gap: 20px;
    font-size: 13px;
    margin-bottom: 28px;
    flex-wrap: wrap;
  }}
  .legend-item {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .legend-box {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
  }}
  .legend-box.available {{
    background: transparent;
    border: 1.5px solid #6b7280;
  }}
  .legend-box.selected {{
    background: #3b82f6;
  }}
  .legend-box.sold {{
    background: var(--seat-sold);
  }}
  .seat-map-wrapper {{
    overflow-x: auto;
    padding: 10px 4px 20px;
  }}
  .seat-grid {{
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: fit-content;
    margin: 0 auto;
    width: fit-content;
  }}
  .seat-row {{
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .row-label {{
    width: 24px;
    font-weight: 700;
    font-size: 14px;
    text-align: center;
    color: var(--text);
  }}
  .seat {{
    width: var(--seat, 28px);
    height: var(--seat, 28px);
    border-radius: 6px;
    font-size: calc(var(--seat, 28px) * 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    user-select: none;
    transition: transform 0.1s;
  }}
  .seat.available {{
    background: #161b22;
    border: 1.5px solid #484f58;
    color: #c9d1d9;
  }}
  .seat.sold {{
    background: #21262d;
    border: 1.5px solid #30363d;
    color: #484f58;
  }}
  .seat.special {{
    border-color: #d29922;
  }}
  .seat.empty-cell {{
    visibility: hidden;
  }}
  .aisle-row {{
    height: 16px;
  }}
  .sampled-note, .photo-note {{
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
  }}
  footer {{
    margin-top: 40px;
    border-top: 1px solid var(--card-border);
    padding-top: 20px;
    text-align: center;
    font-size: 13px;
    color: var(--text-muted);
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Butaca — Mapa de Salas y Butacas Cinépolis</h1>
    <p class="subtitle">Inspección de planos de sala, tipos de butaca y capacidades en Santiago Centro.</p>
  </header>

  <div class="cinema-tabs" id="cinemaTabs">
"""
    cinemas = list(by_cinema.keys())
    for i, cname in enumerate(cinemas):
        active_cls = " active" if i == 0 else ""
        html_content += f'    <button class="tab-btn{active_cls}" data-cinema-idx="{i}">{html.escape(cname)}</button>\n'

    html_content += "  </div>\n\n"

    for i, (cname, rlist) in enumerate(by_cinema.items()):
        disp_style = "block" if i == 0 else "none"
        cinema_id_safe = f"cinema-{i}"
        html_content += f'  <div class="cinema-section" id="{cinema_id_safe}" data-cinema-idx="{i}" style="display: {disp_style};">\n'
        
        # Room chips
        html_content += '    <div class="room-chips">\n'
        for rm in rlist:
            rname = rm.get("room_name", "Sala")
            room_anchor = f"{cinema_id_safe}-{rname.lower().replace(' ', '-')}"
            html_content += f'      <a class="room-chip" href="#{room_anchor}">{html.escape(rname)}</a>\n'
        html_content += "    </div>\n\n"

        # Rooms
        for rm in rlist:
            rname = rm.get("room_name", "Sala")
            room_anchor = f"{cinema_id_safe}-{rname.lower().replace(' ', '-')}"
            formats = rm.get("formats") or ([rm["format"]] if rm.get("format") else ["Tradicional"])
            badges = "".join(f'<span class="badge">{html.escape(f)}</span>' for f in formats)
            sampled_at = rm.get("sampled_at")
            sampled_html = (
                f'<div class="sampled-note">Ocupación muestreada el {html.escape(sampled_at)}</div>'
                if sampled_at else ""
            )
            seat_image = rm.get("seat_image")
            seat_desc = rm.get("seat_description") or "Butaca con diseño ergonómico y portavasos."
            total_seats = rm.get("total_seats", 0)
            rows = [r for r in rm.get("rows", []) if r.get("seats")]
            row_count = len(rows)
            aisles_after = set(rm.get("aisles_after") or [])
            min_col = rm.get("min_col", 0)
            max_col = rm.get("max_col", 0)

            html_content += f"""    <article class="room-card" id="{room_anchor}">
      <div class="room-header">
        <div>
          <div class="room-title">
            {html.escape(rname)}
            {badges}
          </div>
          <div class="room-meta">{total_seats} butacas distribuidas en {row_count} filas</div>
          {sampled_html}
        </div>
      </div>
"""
            if seat_image:
                html_content += f"""      <div class="seat-type-preview">
        <img class="seat-type-icon" src="{html.escape(seat_image)}" alt="Tipo de butaca" />
        <div>
          <strong>Tipo de butaca:</strong> {html.escape(seat_desc)}
          <div class="photo-note">Cinépolis no publica foto de la sala</div>
        </div>
      </div>
"""

            html_content += f"""      <div class="screen-bar">PANTALLA | {html.escape(rname.upper())}</div>

      <div class="legend">
        <div class="legend-item"><div class="legend-box available"></div> Disponible</div>
        <div class="legend-item"><div class="legend-box sold"></div> Ocupado / No disponible</div>
      </div>

      <div class="seat-map-wrapper">
        <div class="seat-grid" style="--seat: {_seat_size(max_col - min_col + 1)}px">
"""
            # Rows arrive normalized (screen -> back, seats col-descending, no empty rows)
            for r in rows:
                pname = r.get("name") or ""
                seats_by_col = {st["col"]: st for st in r["seats"]}
                html_content += '          <div class="seat-row">\n'
                html_content += f'            <div class="row-label">{html.escape(pname)}</div>\n'

                # Mirror of the site: highest columnIndex on the left, down to min_col (0 included)
                for c in range(max_col, min_col - 1, -1):
                    st = seats_by_col.get(c)
                    if st is None:
                        html_content += '            <div class="seat empty-cell"></div>\n'
                        continue
                    status = st.get("status", "Empty")
                    seat_cls = "available" if status == "Empty" else "sold"
                    if st.get("style", "Normal") != "Normal":
                        seat_cls += " special"
                    sid = st.get("id") or ""
                    html_content += f'            <div class="seat {seat_cls}" title="Fila {html.escape(pname)} Asiento {html.escape(sid)} ({html.escape(status)})">{html.escape(sid)}</div>\n'

                html_content += f'            <div class="row-label">{html.escape(pname)}</div>\n'
                html_content += "          </div>\n"
                if pname in aisles_after:
                    html_content += '          <div class="aisle-row"></div>\n'

            html_content += """        </div>
      </div>
    </article>
"""
        html_content += "  </div>\n\n"

    html_content += """  <footer>
    Generado automáticamente por el scraper de Butaca (que-ver-cine-hoy) &bull; Datos extraídos de Cinépolis Chile.
  </footer>
</div>

<script>
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const idx = btn.getAttribute('data-cinema-idx');
    document.querySelectorAll('.tab-btn').forEach(t =>
      t.classList.toggle('active', t.getAttribute('data-cinema-idx') === idx));
    document.querySelectorAll('.cinema-section').forEach(sec => {
      sec.style.display = sec.getAttribute('data-cinema-idx') === idx ? 'block' : 'none';
    });
  });
});
</script>
</body>
</html>
"""

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    return str(out_file)
