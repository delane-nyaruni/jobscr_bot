from collections import defaultdict
from scrapping_engine.models import JobLead
from utilities.seed_utils import load_json

def generate_global_map(html=False):
    """Generates an ASCII bar chart (text) or a minimal HTML dashboard map."""
    country_map = load_json('country_to_continent.json')
    
    leads = JobLead.objects.all()
    if not leads.exists():
        return ""

    country_counts = defaultdict(int)
    for lead in leads:
        country_key = lead.country.lower().strip()
        
        # Clean up old data glitches
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
    # 1. ASCII MAP (For text fallback)
    # ---------------------------------------------------------
    if not html:
        map_lines = ["\nJobscr Behemoth Global Country Reach", "-" * 55]
        for country_name, count in sorted_countries:
            bar_length = int((count / max_count) * 20)
            bar = "█" * max(1, bar_length)
            map_lines.append(f"[{country_name:<20}] {bar:<20} ({count} leads)")
        map_lines.append("-" * 55)
        return "\n".join(map_lines)

    # ---------------------------------------------------------
    # 2. HTML MINIMALIST MAP DASHBOARD (For email)
    # ---------------------------------------------------------
    # A simple, clean embedded SVG map (no external links)
    svg_map = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1000 500' style='width:100%; height:auto; background-color:#ffffff; max-height: 250px;'>"
        "<path fill='#e0e0e0' d='M150 100c-40 0-60 30-60 80s30 80 60 80 60-30 60-80-20-80-60-80zm300-20c-50 0-80 40-80 100s30 100 80 100 80-40 80-100-30-100-80-100zm250 50c-40 0-60 20-60 60s20 60 60 60 60-20 60-60-20-60-60-60zm150 150c-30 0-50 20-50 50s20 50 50 50 50-20 50-50-20-50-50-50zM100 300c-30 0-50 20-50 60s20 80 50 80 50-40 50-80-20-60-50-60zm100 100c-20 0-30 10-30 40s10 40 30 40 30-10 30-40-10-40-30-40zm600-250c-40 0-60 20-60 50s20 50 60 50 60-20 60-50-20-50-60-50z' />"
        "</svg>"
    )

    # Build the HTML layout (Table-based for maximum email client compatibility)
    html_output = f"""
    <div style="max-width: 600px; margin: 0 auto; padding: 15px; border: 1px solid #dddddd; border-radius: 8px; background-color: #f9f9f9; font-family: Arial, sans-serif;">
        <h3 style="margin-top: 0; margin-bottom: 10px; color: #333333; text-align: center;">Global Reach Dashboard</h3>
        <div style="text-align: center; margin-bottom: 15px;">
            {svg_map}
        </div>
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="background-color: #333333; color: #ffffff;">
                    <th style="padding: 8px; text-align: left; border: 1px solid #dddddd;">Country</th>
                    <th style="padding: 8px; text-align: right; border: 1px solid #dddddd;">Leads Found</th>
                </tr>
            </thead>
            <tbody>
    """

    for country_name, count in sorted_countries:
        html_output += f"""
                <tr>
                    <td style="padding: 8px; border: 1px solid #dddddd; color: #333333;">{country_name}</td>
                    <td style="padding: 8px; border: 1px solid #dddddd; text-align: right; color: #2ecc71; font-weight: bold;">{count}</td>
                </tr>
        """

    html_output += """
            </tbody>
        </table>
    </div>
    """
    return html_output