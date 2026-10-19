from collections import defaultdict
from scrapping_engine.models import JobLead
from utilities.seed_utils import load_json

def generate_global_map(html=False):
    """Generates an ASCII bar chart of leads grouped by continent."""
    country_map = load_json('country_to_continent.json')
    
    leads = JobLead.objects.all()
    if not leads.exists():
        return ""

    continent_counts = defaultdict(int)
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
            
        continent = country_map.get(country_key)
        
        # If country not found in JSON, use the Country Name itself instead of "Other"
        if not continent:
            continent = country_key.title() 
        
        continent_counts[continent] += 1

    sorted_continents = sorted(continent_counts.items(), key=lambda x: x[1], reverse=True)
    max_count = max(continent_counts.values()) if continent_counts else 1
    
    # WIDER MAP FORMATTING
    map_lines = ["\nJobscr Behemoth Global Continent Reach", "-" * 65]
    
    for continent, count in sorted_continents:
        # INCREASED BAR LENGTH TO 20 BLOCKS
        bar_length = int((count / max_count) * 20)
        bar = "█" * max(1, bar_length)
        
        if html:
            # Green color for HTML email
            bar = f'<span style="color: #2ecc71;">{bar}</span>'
            
        map_lines.append(f"[{continent:<18}] {bar:<40} ({count} leads)")
        
    map_lines.append("\n")
    return "\n".join(map_lines)