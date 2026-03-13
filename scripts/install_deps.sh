#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Dependencies installed successfully!"
echo "You can now run: python main.py"
