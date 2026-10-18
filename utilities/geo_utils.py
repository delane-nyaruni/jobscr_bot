from collections import defaultdict
from scrapping_engine.models import JobLead

COUNTRY_TO_CONTINENT = {
    "zimbabwe": "Africa", "south africa": "Africa", "zambia": "Africa", 
    "mozambique": "Africa", "botswana": "Africa", "namibia": "Africa", 
    "nigeria": "Africa", "kenya": "Africa", "ghana": "Africa", "egypt": "Africa",
    "uk": "Europe", "united kingdom": "Europe", "england": "Europe", 
    "ireland": "Europe", "germany": "Europe", "france": "Europe", 
    "spain": "Europe", "italy": "Europe", "netherlands": "Europe",
    "usa": "North America", "united states": "North America", 
    "canada": "North America", "mexico": "North America",
    "brazil": "South America", "argentina": "South America",
    "india": "Asia", "china": "Asia", "japan": "Asia", "singapore": "Asia",
    "australia": "Oceania", "new zealand": "Oceania"
}

def generate_global_map():
    """Generates an ASCII bar chart of leads grouped by continent."""
    leads = JobLead.objects.all()
    if not leads.exists():
        return ""

    continent_counts = defaultdict(int)
    for lead in leads:
        country_key = lead.country.lower().strip()
        continent = COUNTRY_TO_CONTINENT.get(country_key, "Other / Global")
        continent_counts[continent] += 1

    sorted_continents = sorted(continent_counts.items(), key=lambda x: x[1], reverse=True)
    max_count = max(continent_counts.values()) if continent_counts else 1
    
    map_lines = ["\n🌍 BEHEMOTH GLOBAL REACH MAP", "-" * 49]
    
    for continent, count in sorted_continents:
        bar_length = int((count / max_count) * 20)
        bar = "█" * max(1, bar_length)
        map_lines.append(f"[{continent:<15}] {bar:<20} ({count} leads)")
        
    map_lines.append("-" * 49)
    return "\n".join(map_lines)