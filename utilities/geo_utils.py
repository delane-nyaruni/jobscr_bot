import os
import io
from collections import defaultdict
from PIL import Image, ImageDraw
from django.conf import settings
from scrapping_engine.models import JobLead
from utilities.seed_utils import load_json

def generate_dynamic_map_image(country_counts):
    """Draws green target circles on the map based on JSON percentages."""
    map_path = os.path.join(settings.MEDIA_ROOT, 'svg', 'world_map.png')
    
    if not os.path.exists(map_path):
        print(f"[!] Map image not found at {map_path}. Please add world_map.png to media/svg/")
        return None

    try:
        # Load the map image
        base_img = Image.open(map_path).convert("RGBA")
        width, height = base_img.size
        
        # Create a transparent overlay for the green highlights
        overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Load the coordinates from the JSON file
        coord_map = load_json('country_to_continent.json')

        for country, count in country_counts.items():
            country_key = country.lower().strip()
            
            # Find the country in the JSON
            location = coord_map.get(country_key)
            if not location or "top" not in location or "left" not in location:
                continue # Skip if country not found or missing coords

            # Convert percentage strings (e.g., "73%") to floats
            try:
                top_pct = float(location["top"].replace("%", "")) / 100.0
                left_pct = float(location["left"].replace("%", "")) / 100.0
            except ValueError:
                continue

            # Calculate exact X, Y pixels
            x = int(width * left_pct)
            y = int(height * top_pct)

            # Calculate radius based on lead count (min 8px, max 35px)
            radius = min(35, 8 + (count * 2))
            
            # Draw a glowing effect (outer faint circle, inner bright circle)
            outer_radius = radius + 6
            draw.ellipse(
                [x - outer_radius, y - outer_radius, x + outer_radius, y + outer_radius],
                fill=(46, 204, 113, 60) # Faint green glow
            )
            draw.ellipse(
                [x - radius, y - radius, x + radius, y + radius],
                fill=(46, 204, 113, 200), # Solid green center
                outline=(255, 255, 255, 255), # White border for contrast
                width=2
            )

        # Combine the base map with the overlay
        combined = Image.alpha_composite(base_img, overlay).convert("RGB")

        # Save to a bytes buffer
        buffer = io.BytesIO()
        combined.save(buffer, format="PNG")
        buffer.seek(0)
        
        return buffer
        
    except Exception as e:
        print(f"[!] Error processing map image: {e}")
        return None


def generate_global_map(html=False):
    """Generates an ASCII bar chart (text) or a clean HTML map + green bars."""
    country_map = load_json('country_to_continent.json')
    
    leads = JobLead.objects.all()
    if not leads.exists():
        return "" if not html else ("", None)

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
    # 2. HTML LIGHT-THEME MAP + GREEN BARS
    # ---------------------------------------------------------
    
    # Generate the dynamic image buffer
    map_buffer = generate_dynamic_map_image(country_counts)
    
    # If the map loaded successfully, create the <img> tag with CID
    map_image_html = ""
    if map_buffer:
        map_image_html = '<img src="cid:global_map" alt="World Map" style="width: 100%; max-width: 650px; height: auto; border: 1px solid #eeeeee; border-radius: 2px;">'
    else:
        map_image_html = "<p style='color: #ff0000;'>[Map image could not be generated. Check server logs.]</p>"

    bars_html = ""
    for country_name, count in sorted_countries:
        bar_length = int((count / max_count) * 20)
        bar = "█" * max(1, bar_length)
        
        # Wrap the bar in a green span
        green_bar = f'<span style="color: #2ecc71; font-weight: bold;">{bar}</span>'
        
        # Escape spaces for HTML rendering
        display_name = country_name.replace(" ", "&nbsp;")
        
        bars_html += f"<div style='margin-bottom: 4px;'>[{display_name:<18}]: &nbsp;{green_bar}&nbsp; ({count} leads)</div>"

    html_output = f"""
    <div style="max-width: 650px; margin: 0 auto; padding: 10px;background-color: #ffffff; font-family: 'Courier New', monospace;">
        <h3 style="margin-top: 0; margin-bottom: 10px; color: #333333; text-align: center; font-family: Arial, sans-serif;">Global Reach Map</h3>
        
        <div style="text-align: center; margin-bottom: 20px;">
            {map_image_html}
        </div>

        <div style="font-size: 13px; margin: auto 0, color: #333333;">
            <div style="margin-bottom: 8px; font-weight: bold; color: #000000;">Jobscr Behemoth Global Country Reach</div>
            <div style="border-top: 1px dashed #cccccc; margin-bottom: 8px;"></div>
            {bars_html}
        </div>
    </div>
    """
    
    return html_output, map_buffer