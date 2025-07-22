#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Setting up WiseBid AI Service...${NC}"

# Check if pyenv is installed
if ! command -v pyenv &> /dev/null; then
    echo -e "${YELLOW}⚠️  pyenv not found. Installing...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install pyenv
    else
        # Linux
        curl https://pyenv.run | bash
    fi

    # Add pyenv to shell configuration
    SHELL_CONFIG="$HOME/.zshrc"
    if [[ "$SHELL" == *"bash"* ]]; then
        SHELL_CONFIG="$HOME/.bashrc"
    fi

    # Add pyenv initialization to shell config if not already present
    if ! grep -q "pyenv init" "$SHELL_CONFIG"; then
        echo 'export PYENV_ROOT="$HOME/.pyenv"' >> "$SHELL_CONFIG"
        echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> "$SHELL_CONFIG"
        echo 'eval "$(pyenv init --path)"' >> "$SHELL_CONFIG"
        echo 'eval "$(pyenv init -)"' >> "$SHELL_CONFIG"
    fi

    # Initialize pyenv in current shell
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init --path)"
    eval "$(pyenv init -)"

    # Reload shell configuration
    source "$SHELL_CONFIG"
fi

# Check if Python 3.11 is installed
if ! pyenv versions | grep -q "3.11"; then
    echo -e "${YELLOW}⚠️  Python 3.11 not found. Installing...${NC}"
    pyenv install 3.11.0
fi

# Set local Python version
echo -e "${GREEN}📦 Setting Python version to 3.11.0...${NC}"
pyenv local 3.11.0

# Reload pyenv shims
pyenv rehash

# Verify Python version
echo -e "${GREEN}🔍 Verifying Python version...${NC}"
python --version

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo -e "${YELLOW}⚠️  Poetry not found. Installing...${NC}"
    curl -sSL https://install.python-poetry.org | python3 -

    # Add Poetry to PATH if not already present
    SHELL_CONFIG="$HOME/.zshrc"
    if [[ "$SHELL" == *"bash"* ]]; then
        SHELL_CONFIG="$HOME/.bashrc"
    fi

    if ! grep -q "/.local/bin" "$SHELL_CONFIG"; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_CONFIG"
    fi
    export PATH="$HOME/.local/bin:$PATH"

    # Reload shell configuration
    source "$SHELL_CONFIG"
fi

# Configure Poetry
echo -e "${GREEN}⚙️  Configuring Poetry...${NC}"
poetry config virtualenvs.in-project true
poetry config virtualenvs.create true

# Install dependencies
echo -e "${GREEN}📚 Installing dependencies...${NC}"
poetry install

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Creating .env file...${NC}"
    cp .env.example .env
fi

echo -e "${GREEN}✅ Setup complete!${NC}"
echo -e "${YELLOW}Please run the following command to activate the changes:${NC}"
echo -e "  ${GREEN}source $SHELL_CONFIG${NC}"
echo -e "${YELLOW}Then you can:${NC}"
echo -e "  ${GREEN}poetry shell${NC}"
echo -e "${YELLOW}To run the application, use:${NC}"
echo -e "  ${GREEN}poetry run python -m app.main${NC}"
