import argparse
import os
import re
import sys

# Mirror of the gear settings
GEARS = {
    "A": {
        "name": "OVERDRIVE",
        "profile": "--load",
        "apps": 50,
        "delay": 20,
        "timeout": 25,
        "cron": "*/30 * * * *",
        "throughput": "~100 emails/hr"
    },
    "B": {
        "name": "CRUISE",
        "profile": "--standard",
        "apps": 20,
        "delay": 30,
        "timeout": 15,
        "cron": "*/15 * * * *",
        "throughput": "~80 emails/hr"
    },
    "C": {
        "name": "ECO",
        "profile": "--tests",
        "apps": 10,
        "delay": 40,
        "timeout": 15,
        "cron": "*/10 * * * *",
        "throughput": "~60 emails/hr"
    },
    "D": {
        "name": "TORQUE",
        "profile": "--heavy",
        "apps": 30,
        "delay": 40,
        "timeout": 25,
        "cron": "*/30 * * * *",
        "throughput": "~60 emails/hr"
    }
}

# Calculate project root (assuming this script is in /utilities/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def detect_active_gear():
    """Reads the actual Python and YAML files to see what gear is currently installed."""
    print("\n" + "="*55)
    print(" JOBSCR BEHEMOTH ENGINE: LIVE DIAGNOSTICS")
    print("="*55)

    py_path = os.path.join(BASE_DIR, 'mailing_engine', 'scripts', 'apply_jobs.py')
    yml_path = os.path.join(BASE_DIR, '.github', 'workflows', 'mailing_robot.yml')

    if not os.path.exists(py_path) or not os.path.exists(yml_path):
        print(" [X] ENGINE OFFLINE: Could not locate apply_jobs.py or mailing_robot.yml")
        print("     Please ensure you are running this from the project root.")
        return

    # Read Python File
    with open(py_path, 'r', encoding='utf-8') as f:
        py_content = f.read()

    # Read YAML File
    with open(yml_path, 'r', encoding='utf-8') as f:
        yml_content = f.read()

    # Extract Python Variables using Regex
    apps_match = re.search(r'MAX_APPLICATIONS_PER_RUN\s*=\s*(\d+)', py_content)
    delay_match = re.search(r'RATE_LIMIT_SECONDS\s*=\s*(\d+)', py_content)
    
    # Extract YAML Variables using Regex
    timeout_match = re.search(r'timeout-minutes:\s*(\d+)', yml_content)
    cron_match = re.search(r"cron:\s*['\"]([^'\"]+)['\"]", yml_content)
    if not cron_match:
        cron_match = re.search(r"cron:\s*([^\s]+)", yml_content)

    # Set fallbacks if not found
    current_apps = int(apps_match.group(1)) if apps_match else 0
    current_delay = int(delay_match.group(1)) if delay_match else 0
    current_timeout = int(timeout_match.group(1)) if timeout_match else 0
    current_cron = cron_match.group(1).strip() if cron_match else "Unknown"

    print(f" [*] Scanning Python: Batch={current_apps}, Delay={current_delay}s")
    print(f" [*] Scanning YAML  : Timeout={current_timeout}m, Cron={current_cron}")

    # Check against known gears
    active_gear = None
    for key, gear in GEARS.items():
        if (gear['apps'] == current_apps and 
            gear['delay'] == current_delay and 
            gear['timeout'] == current_timeout and 
            gear['cron'] == current_cron):
            active_gear = (key, gear)
            break

    print("-" * 55)
    if active_gear:
        print(f" [OK] STATUS: HEALTHY")
        print(f" [GEAR] ACTIVATED: {active_gear[0]} ({active_gear[1]['name']})")
        print(f" [PROFILE] {active_gear[1]['profile']}")
        print(f" [THROUGHPUT] {active_gear[1]['throughput']}")
    else:
        print(" [!!!] STATUS: MALFUNCTION / OVERHEATING")
        print(" [X] The current Python and YAML settings do not match any known gear.")
        print(" [X] There is a mismatch between your .py and .yml files.")
        print(" [!] Please use one of the gear profiles below to sync them.")
    print("="*55 + "\n")


def show_gear(gear_key):
    """Prints the required settings to switch to a specific gear."""
    gear = GEARS.get(gear_key.upper())
    if not gear:
        print(f"Error: Gear '{gear_key}' not found. Choose from A, B, C, or D.")
        return

    print("\n" + "="*55)
    print(f" GEAR {gear_key.upper()}: {gear['name']}  {gear['profile']}")
    print("="*55)
    
    print("\n--- COPY TO PYTHON SCRIPT (apply_jobs.py) ---")
    print(f"MAX_APPLICATIONS_PER_RUN = {gear['apps']}")
    print(f"RATE_LIMIT_SECONDS = {gear['delay']}")
    
    print("\n--- COPY TO YAML FILE (.github/workflows/mailing_robot.yml) ---")
    print(f"timeout-minutes: {gear['timeout']}")
    print(f"cron: '{gear['cron']}'")
    
    print(f"\n>>> ESTIMATED THROUGHPUT: {gear['throughput']}")
    print("="*55 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jobscr Behemoth Gear Ratio Configuration Tool")
    
    # Add positional argument for A, B, C, D
    parser.add_argument("gear", nargs="?", help="Gear letter (A, B, C, D)")
    
    # Add flags for the profiles
    parser.add_argument("--load", action="store_true", help="Show settings for Gear A (Overdrive)")
    parser.add_argument("--standard", action="store_true", help="Show settings for Gear B (Cruise)")
    parser.add_argument("--tests", action="store_true", help="Show settings for Gear C (Eco)")
    parser.add_argument("--heavy", action="store_true", help="Show settings for Gear D (Torque)")

    args = parser.parse_args()

    # Determine what to run
    if args.load or args.gear == "A" or args.gear == "a":
        show_gear("A")
        detect_active_gear()
    elif args.standard or args.gear == "B" or args.gear == "b":
        show_gear("B")
        detect_active_gear()
    elif args.tests or args.gear == "C" or args.gear == "c":
        show_gear("C")
        detect_active_gear()
    elif args.heavy or args.gear == "D" or args.gear == "d":
        show_gear("D")
        detect_active_gear()
    else:
        # If no arguments are passed, just run the diagnostic scan
        detect_active_gear()
        print("Usage: python utilities/gears_ratio_settings.py [A/B/C/D] OR [--load/--standard/--tests/--heavy]")
        print("Available gears:")
        for k, v in GEARS.items():
            print(f"  {k}: {v['name']:<10} {v['profile']:<10} | ~{v['throughput']}\n")