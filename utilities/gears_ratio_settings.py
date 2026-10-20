import argparse
import os
import re
import sys

GEARS = {
    "A": {"name": "OVERDRIVE", "profile": "--load (High-Speed/High-Volume)", "apps": 50, "delay": 20, "timeout": 25, "cron": "*/30 * * * *"},
    "B": {"name": "CRUISE", "profile": "--standard (Balanced/Fast-Rest)", "apps": 20, "delay": 30, "timeout": 15, "cron": "*/15 * * * *"},
    "C": {"name": "ECO", "profile": "--tests (Low-Volume/Quick-Fire)", "apps": 10, "delay": 40, "timeout": 15, "cron": "*/10 * * * *"},
    "D": {"name": "TORQUE", "profile": "--heavy (Heavy-Lift/Long-Rest)", "apps": 30, "delay": 40, "timeout": 25, "cron": "*/30 * * * *"}
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP_TIME = 3.0


def parse_cron_interval(cron_str):
    try:
        if cron_str.startswith("*/"):
            return int(cron_str.split()[0].replace("*/", ""))
        elif cron_str.split()[0] == "0":
            return 60
        return 60
    except:
        return 60


def calculate_math(apps, delay, timeout, cron):
    """Calculate the runtime math and safety warnings."""
    interval = parse_cron_interval(cron)
    process_time = (apps * delay) / 60
    total_runtime = process_time + SETUP_TIME
    rest_time = interval - total_runtime
    throughput = apps * (60 / interval)

    warnings = []
    if total_runtime > timeout:
        warnings.append(f"Total Runtime ({total_runtime:.1f} mins) EXCEEDS GitHub Set Timeout ({timeout} mins)")
    if total_runtime > interval:
        warnings.append(f"Total Runtime ({total_runtime:.1f} mins) EXCEEDS Cron Set Interval ({interval} mins) -> QUEUE OVERLAP")
    if rest_time < 0:
        warnings.append(f"Negative Rest Time ({rest_time:.1f} mins) -> ENGINE OVERHEAT")

    return {
        "apps": apps, "delay": delay, "timeout": timeout, "cron": cron,
        "interval": interval, "process_time": process_time,
        "total_runtime": total_runtime, "rest_time": rest_time,
        "throughput": throughput, "warnings": warnings
    }


def print_math_block(result):
    print("RATIO MATH:")
    print(f"- Processing:     {result['apps']} apps * {result['delay']} sec = {result['apps']*result['delay']} sec ({result['process_time']:.1f} mins)")
    print(f"- Setup Overhead: {SETUP_TIME:.1f} mins")
    print(f"- Total Runtime:  {result['total_runtime']:.1f} mins")
    print(f"- Rest Time:      {result['rest_time']:.1f} mins")
    print(f"- THROUGHPUT:     ~{result['throughput']:.0f} emails per hour")


def match_gear(apps, delay, timeout, cron):
    """Finds an exact match for the predefined gears."""
    for key, gear in GEARS.items():
        if (gear['apps'] == apps and gear['delay'] == delay and
                gear['timeout'] == timeout and gear['cron'] == cron):
            return key, gear
    return None, None


def find_closest_gear_by_throughput(custom_throughput):
    """Finds the closest predefined gear based on throughput performance and calculates the delta."""
    closest_key = None
    min_diff = float('inf')
    delta = 0
    
    for key, gear in GEARS.items():
        interval = parse_cron_interval(gear['cron'])
        gear_throughput = gear['apps'] * (60 / interval)
        diff = abs(custom_throughput - gear_throughput)
        
        if diff < min_diff:
            min_diff = diff
            closest_key = key
            # Calculate actual delta (custom - gear) for the + or - sign
            delta = custom_throughput - gear_throughput
            
    return closest_key, GEARS[closest_key], delta


def read_current_files():
    py_path = os.path.join(BASE_DIR, 'mailing_engine', 'scripts', 'apply_jobs.py')
    yml_path = os.path.join(BASE_DIR, '.github', 'workflows', 'mailing_robot.yml')

    if not os.path.exists(py_path) or not os.path.exists(yml_path):
        return None

    with open(py_path, 'r', encoding='utf-8') as f:
        py_content = f.read()
    with open(yml_path, 'r', encoding='utf-8') as f:
        yml_content = f.read()

    apps_match = re.search(r'MAX_APPLICATIONS_PER_RUN\s*=\s*(\d+)', py_content)
    delay_match = re.search(r'RATE_LIMIT_SECONDS\s*=\s*(\d+)', py_content)
    timeout_match = re.search(r'timeout-minutes:\s*(\d+)', yml_content)
    cron_match = re.search(r"cron:\s*['\"]([^'\"]+)['\"]", yml_content)
    if not cron_match:
        cron_match = re.search(r"cron:\s*([^\s]+)", yml_content)

    return {
        "apps": int(apps_match.group(1)) if apps_match else 0,
        "delay": int(delay_match.group(1)) if delay_match else 0,
        "timeout": int(timeout_match.group(1)) if timeout_match else 0,
        "cron": cron_match.group(1).strip() if cron_match else "Unknown"
    }


def print_gear_list():
    print("\nAVAILABLE GEARS (Full Specs)")
    print("=" * 110)
    print(f"  {'KEY':<4} {'NAME':<11} {'FLAG':<11} {'BATCH':<6} {'DELAY':<6} {'TIMEOUT':<8} {'CRON':<16} {'THROUGHPUT':<15} {'DESCRIPTION':<28}")
    print("=" * 110)
    for k, v in GEARS.items():
        interval = parse_cron_interval(v['cron'])
        throughput = v['apps'] * (60 / interval)
        
        # Split profile like "--load (High Speed / High Volume)" into FLAG and DESCRIPTION
        if "(" in v['profile']:
            flag = v['profile'].split("(")[0].strip()
            desc = v['profile'].split("(")[1].rstrip(")").strip()
        else:
            flag = v['profile']
            desc = ""
            
        print(f"  {k}   {v['name']:<11} {flag:<11} {v['apps']:<6} {v['delay']}s{'':<3} {v['timeout']}m{'':<5} {v['cron']:<16} ~{throughput:.0f} emails/hr{'':<2} {desc:<28}")
    # print("-" * 110 + "\n")


def detect_active_gear():
    print("\n" + "=" * 105)
    print(" JOBSCR BEHEMOTH ENGINE: LIVE DIAGNOSTICS")
    print("=" * 105)

    current = read_current_files()
    if not current:
        print(" [X] ENGINE OFFLINE: Could not locate apply_jobs.py or mailing_robot.yml")
        return

    print(f" [*] Scanning Python: Batch={current['apps']}, Delay={current['delay']}s")
    print(f" [*] Scanning YAML  : Timeout={current['timeout']}m, Cron={current['cron']}")

    matched_key, matched_gear = match_gear(current['apps'], current['delay'], current['timeout'], current['cron'])
    result = calculate_math(current['apps'], current['delay'], current['timeout'], current['cron'])

    print("-" * 105)
    if matched_key:
        print(f" [OK] STATUS: HEALTHY - Running GEAR {matched_key} ({matched_gear['name']}) {matched_gear['profile']}")
    else:
        closest_key, closest_gear, delta = find_closest_gear_by_throughput(result['throughput'])
        diff_sign = "+" if delta >= 0 else ""
        print(f" [~]  STATUS: CUSTOM GEAR - Not matching predefined gears exactly.")
        print(f"      Performance Tier: Near GEAR {closest_key} ({closest_gear['name']}) based on throughput. (Delta: {diff_sign}{delta:.0f} emails/hr)")

    if result['warnings']:
        print(f" [!!!] SAFETY: ENGINE OVERHEATING - {len(result['warnings'])} issue(s) detected")
    else:
        print(f" [OK] SAFETY: All checks passed - INBOUND RANGE ")

    print(f" [SPECS] Batch={current['apps']} | Delay={current['delay']}s | Timeout={current['timeout']}m | Cron={current['cron']} | ~{result['throughput']:.0f} emails/hr")
    print("-" * 105)
    print_math_block(result)

    if result['warnings']:
        print("-" * 105)
        print(" [!!!] SAFETY WARNINGS:")
        for w in result['warnings']:
            print(f"   [X] {w}")

    print("=" * 105 + "\n")


def show_gear(gear_key):
    gear = GEARS.get(gear_key.upper())
    if not gear:
        print(f"Error: Gear '{gear_key}' not found. Choose from A, B, C, or D.")
        return

    result = calculate_math(gear['apps'], gear['delay'], gear['timeout'], gear['cron'])

    print("\n" + "=" * 105)
    print(f" GEAR {gear_key.upper()}: {gear['name']}  {gear['profile']}  |  ~{result['throughput']:.0f} emails/hr")
    print("=" * 105)
    print("\n--- COPY TO PYTHON SCRIPT (apply_jobs.py) ---")
    print(f"MAX_APPLICATIONS_PER_RUN = {gear['apps']}")
    print(f"RATE_LIMIT_SECONDS = {gear['delay']}")
    print("\n--- COPY TO YAML FILE (.github/workflows/mailing_robot.yml) ---")
    print(f"timeout-minutes: {gear['timeout']}")
    print(f"cron: '{gear['cron']}'")
    print("-" * 105)
    print_math_block(result)
    if result['warnings']:
        print("-" * 105)
        print(" [!!!] SAFETY WARNINGS:")
        for w in result['warnings']:
            print(f"   [X] {w}")
    print("=" * 105 + "\n")


def run_dynamic(args):
    current = read_current_files()
    if not current:
        print("[X] Could not read current files. Using default fallbacks.")
        current = {"apps": 10, "delay": 40, "timeout": 15, "cron": "*/10 * * * *"}

    apps = args.batch if args.batch else current['apps']
    delay = args.delay if args.delay else current['delay']
    timeout = args.timeout if args.timeout else current['timeout']
    cron = args.cron if args.cron else current['cron']

    result = calculate_math(apps, delay, timeout, cron)
    matched_key, matched_gear = match_gear(apps, delay, timeout, cron)

    print("\n" + "=" * 105)
    print(" DYNAMIC GEAR RATIO SIMULATOR")
    print("=" * 105)
    print(f" [*] Base (from files): Batch={current['apps']}, Delay={current['delay']}s, Timeout={current['timeout']}m, Cron={current['cron']}")

    overrides = []
    if args.batch: overrides.append(f"Batch={args.batch}")
    if args.delay: overrides.append(f"Delay={args.delay}s")
    if args.timeout: overrides.append(f"Timeout={args.timeout}m")
    if args.cron: overrides.append(f"Cron={args.cron}")
    print(f" [*] Overrides Applied: {', '.join(overrides) if overrides else 'None'}")
    print(f" [*] Simulated Values : Batch={apps}, Delay={delay}s, Timeout={timeout}m, Cron={cron}")
    print("-" * 105)

    if matched_key:
        print(f" [OK] GEAR MATCH: {matched_key} ({matched_gear['name']})")
    else:
        closest_key, closest_gear, delta = find_closest_gear_by_throughput(result['throughput'])
        diff_sign = "+" if delta >= 0 else ""
        print(f" [~]  GEAR MATCH: CUSTOM (Not Exact Match)")
        print(f"      Performance Tier: Closest to GEAR {closest_key} ({closest_gear['name']}) based on throughput. (Delta: {diff_sign}{delta:.0f} emails/hr)")

    if result['warnings']:
        print(f" [!!!] SAFETY: ENGINE OVERHAUL - {len(result['warnings'])} issue(s) detected")
    else:
        print(f" [OK] SAFETY: All checks passed - inbound within bounds")

    print("-" * 105)
    print_math_block(result)

    if result['warnings']:
        print("-" * 105)
        print(" [!!!] SAFETY WARNINGS:")
        for w in result['warnings']:
            print(f"   [X] {w}")

    print("=" * 105)

    # Only show APPLY instructions if the config is SAFE
    if result['warnings']:
        print("\n [X] CONFIGURATION REJECTED - DO NOT INSTALL")
        print("     This configuration is out of bounds and would cause engine failure.")
        print("     Adjust your values and try again. Use `--load`, `--standard`,")
        print("     `--tests`, or `--heavy` to load a known safe gear.")
        print("=" * 105)
    elif not matched_key:
        print("\n [!] To APPLY this custom configuration, update both files manually:")
        print(f"     apply_jobs.py     : MAX_APPLICATIONS_PER_RUN = {apps}, RATE_LIMIT_SECONDS = {delay}")
        print(f"     mailing_robot.yml : timeout-minutes: {timeout}, cron: '{cron}'")
        print("=" * 105)
    
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jobscr Behemoth Gear Ratio Configuration Tool")

    parser.add_argument("gear", nargs="?", help="Gear letter (A, B, C, D)")
    parser.add_argument("--load", action="store_true", help="Show settings for Gear A (Overdrive)")
    parser.add_argument("--standard", action="store_true", help="Show settings for Gear B (Cruise)")
    parser.add_argument("--tests", action="store_true", help="Show settings for Gear C (Eco)")
    parser.add_argument("--heavy", action="store_true", help="Show settings for Gear D (Torque)")

    # Dynamic override flags
    parser.add_argument("--batch", type=int, help="Override batch size for dynamic calculation")
    parser.add_argument("--delay", type=int, help="Override delay in seconds")
    parser.add_argument("--timeout", type=int, help="Override timeout in minutes")
    parser.add_argument("--cron", type=str, help="Override cron expression")

    args = parser.parse_args()

    has_dynamic = any([args.batch, args.delay, args.timeout, args.cron])

    if has_dynamic:
        run_dynamic(args)
    elif args.load or args.gear == "A" or args.gear == "a":
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
        detect_active_gear()
        print("STATIC MODE:")
        print("  python utilities/gears_ratio_settings.py [A/B/C/D]")
        print("  python utilities/gears_ratio_settings.py [--load/--standard/--tests/--heavy]")
        print("\nDYNAMIC MODE (custom values):")
        print("  python utilities/gears_ratio_settings.py --batch 32")
        print("  python utilities/gears_ratio_settings.py --batch 35 --delay 30 --timeout 20 --cron \"*/20 * * * *\"")
        print_gear_list()