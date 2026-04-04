"""Smoke test for CSV Analyzer"""
import subprocess, sys

result = subprocess.run(
    [sys.executable, "agent.py", "--mode", "test"],
    capture_output=True, text=True, timeout=150
)
if "TEST_OK" in result.stdout:
    print("SMOKE_PASS")
    sys.exit(0)
else:
    print(f"SMOKE_FAIL: {result.stdout} {result.stderr}")
    sys.exit(1)
