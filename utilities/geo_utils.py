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
        continent = country_map.get(country_key, "Other / Global")
        continent_counts[continent] += 1

    sorted_continents = sorted(continent_counts.items(), key=lambda x: x[1], reverse=True)
    max_count = max(continent_counts.values()) if continent_counts else 1
    
    map_lines = ["\nJOBSCR BEHEMOTH GLOBAL MAP REACH", "-" * 49]
    
    for continent, count in sorted_continents:
        bar_length = int((count / max_count) * 20)
        bar = "█" * max(1, bar_length)
        
        if html:
            # Green color for HTML email
            bar = f'<span style="color: #2ecc71;">{bar}</span>'
            
        map_lines.append(f"[{continent:<15}] {bar:<20} ({count} leads)")
        
    map_lines.append("-" * 49)
    return "\n".join(map_lines)