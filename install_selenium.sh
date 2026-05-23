#!/bin/bash

echo "=================================="
echo "Selenium LinkedIn Scraper Setup"
echo "=================================="
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="Linux"
else
    OS="Unknown"
fi

echo "Detected OS: $OS"
echo ""

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install selenium webdriver-manager
echo "✅ Python dependencies installed"
echo ""

# Install ChromeDriver
if [[ "$OS" == "macOS" ]]; then
    echo "🍎 Installing ChromeDriver for macOS..."
    if command -v brew &> /dev/null; then
        brew install chromedriver
        echo "✅ ChromeDriver installed via Homebrew"
    else
        echo "⚠️  Homebrew not found. Install from: https://brew.sh/"
        echo "Then run: brew install chromedriver"
    fi
elif [[ "$OS" == "Linux" ]]; then
    echo "🐧 Installing ChromeDriver for Linux..."
    sudo apt-get update
    sudo apt-get install -y chromium-browser chromium-chromedriver
    echo "✅ ChromeDriver installed via apt-get"
else
    echo "⚠️  Unknown OS. Please install ChromeDriver manually:"
    echo "   https://chromedriver.chromium.org/"
fi

echo ""
echo "🧪 Testing installation..."
if command -v chromedriver &> /dev/null; then
    echo "✅ ChromeDriver found:"
    chromedriver --version
else
    echo "⚠️  ChromeDriver not found in PATH"
    echo "   Try: export PATH=\$PATH:/usr/local/bin"
fi

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Test with: python3 test_linkedin_verifier.py"
echo "2. Upload resume with LinkedIn URL"
echo "3. Check logs for scraping results"
echo ""
echo "Documentation: SELENIUM_SETUP_GUIDE.md"
