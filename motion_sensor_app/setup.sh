#!/bin/bash
# Setup script for the app environment
# Works on macOS, Linux, and WSL

echo "Setting up Motion Sensor App environment..."

# Check if Python3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed or not in PATH"
    echo "Please install Python 3.8+ first"
    exit 1
fi

echo "Using Python version: $(python3 --version)"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment"
        echo "Try: python3 -m pip install --upgrade pip"
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing server dependencies..."
pip install -r requirements.txt

echo "App setup complete!"
