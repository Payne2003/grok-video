#!/usr/bin/env python3
import subprocess
import sys

packages = ['PySide6', 'playwright', 'requests', 'loguru']

print("Installing required packages...")
for package in packages:
    print(f"\nInstalling {package}...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--quiet', package])

print("\n✓ All dependencies installed successfully!")
