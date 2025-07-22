#!/bin/bash

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Poetry is installed
if ! command_exists poetry; then
    echo -e "${RED}❌ Poetry is not installed. Please install it first:${NC}"
    echo "curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

# Check if we're in a Poetry environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  Not in a Poetry environment. Using poetry run...${NC}"
    # Use poetry run to execute the rest of the script
    # Set PYTHONUNBUFFERED to ensure logs are output immediately
    export PYTHONUNBUFFERED=1
    exec poetry run "$0" "$@"
    exit 0
fi

# Always ensure dependencies are up to date
echo -e "${YELLOW}⚠️  Ensuring all dependencies are installed...${NC}"
poetry install --no-interaction --all-extras

# Check for environment file
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Creating from example...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ Created .env file from example. Please update it with your settings.${NC}"
    else
        echo -e "${RED}❌ No .env.example file found. Please create a .env file manually.${NC}"
    fi
fi

# Set PYTHONUNBUFFERED to ensure logs are output immediately
export PYTHONUNBUFFERED=1

# Run the application
echo -e "${GREEN}🚀 Starting the application...${NC}"
python main.py 