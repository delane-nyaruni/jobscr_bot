from urllib.parse import urlparse
from utilities.seed_utils import load_json

def infer_country_from_url(url):
    """
    Guesses the country based on the domain extension (TLD).
    Loads the TLD mappings from seed/tld_to_country.json.
    Returns a country string or 'Global' if it cannot be determined.
    """
    try:
        domain = urlparse(url).netloc.lower()
        
        # Load the map from the seed folder
        tld_map = load_json('tld_to_country.json')
        
        if not tld_map:
            return 'Global'

        # CRITICAL: Sort keys by length descending.
        # This ensures ".co.uk" is checked BEFORE ".uk", avoiding false matches.
        sorted_tlds = sorted(tld_map.keys(), key=len, reverse=True)

        # Iterate through the sorted TLDs and check if the domain ends with them
        for tld in sorted_tlds:
            if domain.endswith(tld):
                return tld_map[tld]

        # If it ends in .com, .org, .net, etc., we assume it's Global or US
        if domain.endswith('.com') or domain.endswith('.org') or domain.endswith('.net'):
            return 'Global' 
            
        return 'Global'

    except Exception:
        return 'Global'