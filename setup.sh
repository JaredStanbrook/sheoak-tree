#!/bin/bash
# Setup script for the app environment
# Works on macOS, Linux, and WSL

# --- Configuration ---
# The file that contains "app = create_app()"
FLASK_ENTRY_FILE="run.py"
# ---------------------

echo "Setting up Sheoak Tree environment..."

# 1. Check Python availability
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed or not in PATH"
    echo "Please install Python 3.8+ first"
    exit 1
fi

echo "Using Python version: $(python3 --version)"

# 2. Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment."
        exit 1
    fi
else
    echo "Virtual environment already exists."
fi

# 3. Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# 4. Install dependencies
echo "Upgrading pip and installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "------------------------------------------------"
echo "Environment setup complete."
echo "------------------------------------------------"

# 5. Database Initialization Prompt
echo "Would you like to initialize/migrate the database now? (y/N)"
read -r -p "Your choice: " response

if [[ "$response" =~ ^[yY]$ ]]; then
    echo -e "\nInitializing database..."

    # Export the Flask app environment variable so commands work
    export FLASK_APP=$FLASK_ENTRY_FILE

    # Check if the 'migrations' folder exists
    if [ ! -d "migrations" ]; then
        echo "No migrations folder found. Initializing fresh migrations..."
        flask db init
        if [ $? -ne 0 ]; then echo "Error initializing db"; exit 1; fi
        
        flask db migrate -m "Initial setup migration"
        if [ $? -ne 0 ]; then echo "Error creating migration"; exit 1; fi
    else
        echo "Migrations folder found. Checking for updates..."
    fi

    # Apply the migrations (Creates tables)
    echo "Applying database upgrades..."
    flask db upgrade

    if [ $? -eq 0 ]; then
        echo "Database initialized successfully!"
        
        # Optional: Seed data prompt (You can remove this block if not needed)
        # echo "Would you like to seed initial data? (y/N)"
        # read -r -p "Your choice: " seed_response
        # if [[ "$seed_response" =~ ^[yY]$ ]]; then
        #    python -c "from app import create_app, db; app=create_app(); ... your seed logic ..."
        # fi
    else
        echo "Error: Database initialization failed."
        exit 1
    fi
else
    echo -e "\nSkipping database initialization."
fi

echo "App setup finished successfully!"