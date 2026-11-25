from collections import defaultdict
from scrapping_engine.models import JobLead
from utilities.seed_utils import load_json

def generate_global_map(html=False):
    """Generates either an ASCII map or an F1-Style HTML map (Country level)."""
    country_map = load_json('country_to_continent.json')
    
    leads = JobLead.objects.all()
    if not leads.exists():
        return ""

    country_counts = defaultdict(int)
    for lead in leads:
        country_key = lead.country.lower().strip()
        
        # Clean up old data glitches (e.g., "['Zimbabwe', 'United States']")
        if country_key.startswith('[') and country_key.endswith(']'):
            try:
                inner = country_key[1:-1]
                first_country = inner.split(',')[0].replace("'", "").replace('"', '').strip()
                country_key = first_country
            except Exception:
                pass

        if not country_key:
            continue
            
        country_counts[country_key.title()] += 1

    sorted_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)
    max_count = max(country_counts.values()) if country_counts else 1

    # ---------------------------------------------------------
    # HTML MAP RENDERER (F1 STYLE - EXACT COUNTRY)
    # ---------------------------------------------------------
    if html:
        # Basic black world map SVG (embedded)
        svg_map = (
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1000 500' style='width:100%; height:auto; background-color:#ffffff;'>"
            "<path fill='#000000' d='M150 100c-40 0-60 30-60 80s30 80 60 80 60-30 60-80-20-80-60-80zm300-20c-50 0-80 40-80 100s30 100 80 100 80-40 80-100-30-100-80-100zm250 50c-40 0-60 20-60 60s20 60 60 60 60-20 60-60-20-60-60-60zm150 150c-30 0-50 20-50 50s20 50 50 50 50-20 50-50-20-50-50-50zM100 300c-30 0-50 20-50 60s20 80 50 80 50-40 50-80-20-60-50-60zm100 100c-20 0-30 10-30 40s10 40 30 40 30-10 30-40-10-40-30-40zm600-250c-40 0-60 20-60 50s20 50 60 50 60-20 60-50-20-50-60-50z' />"
            "</svg>"
        )

        html_map = f"<div style='position:relative; width:100%; max-width:800px; margin:0 auto; background-color:#ffffff; border:1px solid #dddddd; padding:10px;'>{svg_map}"
        
        for country_name, count in sorted_countries:
            if count > 0:
                # Look up coordinates in the JSON
                data = country_map.get(country_name.lower())
                
                if data and "top" in data and "left" in data:
                    top = data["top"]
                    left = data["left"]
                    html_map += (
                        f"<div style='position:absolute; top:{top}; left:{left}; "
                        f"background-color:#d32f2f; color:#ffffff; padding:3px 8px; "
                        f"border-radius:4px; font-family:Arial,sans-serif; font-size:11px; "
                        f"font-weight:bold; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); z-index:10; "
                        f"border: 1px solid #fff; white-space:nowrap;'>"
                        f"{country_name}: {count}</div>"
                    )
        
        html_map += "</div>"
        return html_map

    # ---------------------------------------------------------
    # ASCII MAP RENDERER (Fallback for text emails)
    # ---------------------------------------------------------
    else:
        map_lines = ["\nJobscr Behemoth Global Country Reach", "-" * 65]
        
        for country_name, count in sorted_countries:
            bar_length = int((count / max_count) * 20)
            bar = "█" * max(1, bar_length)
            map_lines.append(f"[{country_name:<20}] {bar:<20} ({count} leads)")
            
        map_lines.append("-" * 65)
        return "\n".join(map_lines)