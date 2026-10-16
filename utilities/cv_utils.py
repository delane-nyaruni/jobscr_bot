import re


def parse_cv_filename(filename):
    """
    Extracts name and target role from filenames like:
        Delane_Nyaruni_Software_Engineer_CV.pdf
        Delane_Nyaruni_Driver_Class_4_CV.pdf
    Returns a tuple (full_name, target_role) or (None, None) if parsing fails.
    """
    name_without_ext = filename.replace('.pdf', '').replace('.PDF', '')
    parts = name_without_ext.split('_')

    if len(parts) < 3:
        return None, None

    full_name = f"{parts[0]} {parts[1]}"

    if parts[-1].upper() == 'CV':
        role_parts = parts[2:-1]
    else:
        role_parts = parts[2:]

    target_role = " ".join(role_parts)
    return full_name, target_role