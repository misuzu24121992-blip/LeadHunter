"""
Verichains LeadHunter — Runner Script
Runs all three scripts in sequence. Use this for cron jobs.

Usage:
    python run_all.py            # Run all scripts
    python run_all.py --quick    # Skip incident radar (faster)

Cron example (every 6 hours):
    0 */6 * * * cd /path/to/velvet-exoplanet && python run_all.py >> /tmp/leadhunter.log 2>&1
"""

import sys
import subprocess
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_script(name: str) -> bool:
    """Run a Python script and return True if successful."""
    script = os.path.join(SCRIPT_DIR, name)
    print(f"\n{'='*60}")
    print(f"▶️  Running {name}...")
    print(f"{'='*60}")
    try:
        result = subprocess.run(
            [sys.executable, script],
            cwd=SCRIPT_DIR,
            timeout=300,  # 5 min timeout per script
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  ❌ {name} timed out!")
        return False
    except Exception as e:
        print(f"  ❌ {name} failed: {e}")
        return False


def main():
    quick = "--quick" in sys.argv

    print("🚀 Verichains LeadHunter — Full Run")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'Quick (no incident radar)' if quick else 'Full'}")

    scripts = ["lead_hunter.py", "upgrade_watcher.py"]
    if not quick:
        scripts.append("incident_radar.py")

    results = {}
    for script in scripts:
        results[script] = run_script(script)

    # Summary
    print(f"\n{'='*60}")
    print("📊 RUN SUMMARY")
    print(f"{'='*60}")
    for script, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {script}")
    print()
    print("🏁 All done!")


if __name__ == "__main__":
    main()
