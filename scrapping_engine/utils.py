# jobs/utils.py
import re

def parse_cv_filename(filename):
    """
    Extracts name and target role from filenames like:
    Delane_Nyaruni_Software_Engineer_CV.pdf
    Delane_Nyaruni_Driver_Class_4_CV.pdf
    """
    # Remove .pdf extension
    name_without_ext = filename.replace('.pdf', '').replace('.PDF', '')
    
    # Split by underscore
    parts = name_without_ext.split('_')
    
    # The last part is usually 'CV', the first two are the name.
    # The middle parts are the role.
    if len(parts) >= 3:
        full_name = f"{parts[0]} {parts[1]}"
        
        # If the last part is 'CV', ignore it. Otherwise include it in the role.
        if parts[-1].upper() == 'CV':
            role_parts = parts[2:-1]
        else:
            role_parts = parts[2:]
            
        target_role = " ".join(role_parts)
        return full_name, target_role
    
    return None, None

# Example usage in a Django shell or view:
# name, role = parse_cv_filename("Delane_Nyaruni_Software_Engineer_CV.pdf")
# print(name) # Delane Nyaruni
# print(role) # Software Engineer