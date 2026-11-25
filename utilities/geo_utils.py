from collections import defaultdict
from scrapping_engine.models import JobLead
from utilities.seed_utils import load_json

def generate_global_map(html=False):
    """Generates an ASCII bar chart of leads grouped by country with green bars for HTML."""
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
    
    # WIDER MAP FORMATTING
    map_lines = ["\nJobscr Behemoth Global Country Reach", "-" * 65]
    
    for country_name, count in sorted_countries:
        # INCREASED BAR LENGTH TO 20 BLOCKS
        bar_length = int((count / max_count) * 20)
        bar = "█" * max(1, bar_length)
        
        if html:
            # Green color for HTML email bars
            bar = f'<span style="color: #2ecc71;">{bar}</span>'
            
        map_lines.append(f"[{country_name:<18}]:       {bar:<40} ({count} leads)")
        
    map_lines.append("\n")
    return "\n".join(map_lines)