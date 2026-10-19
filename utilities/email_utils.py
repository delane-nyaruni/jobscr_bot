import re
from bs4 import BeautifulSoup
from utilities.seed_utils import load_json

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}'

# Load rules from seed folder
PLACEHOLDER_LOCAL_PARTS = set(load_json('placeholder_local_parts.json'))
PLACEHOLDER_DOMAINS = set(load_json('placeholder_domains.json'))
CSS_NOISE_LOCALS = set(load_json('css_noise_locals.json'))
REJECT_LOCAL_PREFIXES = tuple(load_json('reject_local_prefixes.json'))
VALID_TLDS = tuple(load_json('valid_tlds.json'))


def is_valid_email(email, blacklist):
    """Strict validation — rejects CSS noise, placeholders, admin, invalid TLDs."""
    email = email.lower().strip().rstrip('.,;:')
    if not email or '@' not in email: return False
    if not re.fullmatch(EMAIL_REGEX, email): return False
    
    local, _, domain = email.partition('@')
    if not local or not domain: return False
    if local in CSS_NOISE_LOCALS: return False
    if '..' in domain or domain.startswith('.') or domain.endswith('.'): return False
    if '..' in local or local.startswith('.') or local.endswith('.'): return False
    if local in PLACEHOLDER_LOCAL_PARTS: return False
    if domain in PLACEHOLDER_DOMAINS: return False
    if any(local.startswith(p) for p in REJECT_LOCAL_PREFIXES): return False
    if not any(domain.endswith(tld) for tld in VALID_TLDS): return False
    if any(bl in domain for bl in blacklist): return False
    
    return True


def extract_emails_from_html(html_text, blacklist):
    """Extracts and validates emails, stripping style/script tags first."""
    soup = BeautifulSoup(html_text, 'html.parser')
    for tag in soup(['style', 'script', 'noscript']): 
        tag.decompose()
    clean_text = soup.get_text(separator=' ')
    raw_emails = re.findall(EMAIL_REGEX, clean_text)
    clean = set()
    for email in raw_emails:
        if is_valid_email(email, blacklist):
            clean.add(email.lower().strip())
    return list(clean)