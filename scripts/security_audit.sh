#!/bin/bash
# Security audit script for Crypto Research Platform

set -e

echo "=================================="
echo "Security Audit Report"
echo "Date: $(date)"
echo "=================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create reports directory
REPORT_DIR="security_reports"
mkdir -p "$REPORT_DIR"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REPORT_FILE="$REPORT_DIR/security_audit_$TIMESTAMP.txt"

# Redirect output to both console and file
exec > >(tee -a "$REPORT_FILE")
exec 2>&1

echo "Report will be saved to: $REPORT_FILE"
echo ""

# Check if dependencies are installed
echo "1. Checking security tools..."
echo "=================================="

TOOLS_MISSING=0

if ! command -v bandit &> /dev/null; then
    echo -e "${YELLOW}⚠ bandit not installed${NC}"
    TOOLS_MISSING=1
fi

if ! command -v safety &> /dev/null; then
    echo -e "${YELLOW}⚠ safety not installed${NC}"
    TOOLS_MISSING=1
fi

if ! command -v pip-audit &> /dev/null; then
    echo -e "${YELLOW}⚠ pip-audit not installed${NC}"
    TOOLS_MISSING=1
fi

if [ $TOOLS_MISSING -eq 1 ]; then
    echo ""
    echo "Installing missing tools..."
    pip install bandit safety pip-audit
fi

echo -e "${GREEN}✓ All security tools available${NC}"
echo ""

# Run Bandit security scan
echo "2. Running Bandit code security scan..."
echo "=================================="
echo "Scanning for common security issues in Python code..."
echo ""

if bandit -r src/ -ll -f txt -o "$REPORT_DIR/bandit_$TIMESTAMP.txt"; then
    echo -e "${GREEN}✓ Bandit scan completed - No critical issues found${NC}"
else
    echo -e "${YELLOW}⚠ Bandit found issues - Check $REPORT_DIR/bandit_$TIMESTAMP.txt${NC}"
fi
echo ""

# Run Safety check
echo "3. Running Safety dependency vulnerability check..."
echo "=================================="
echo "Checking for known vulnerabilities in dependencies..."
echo ""

if safety check --json --output "$REPORT_DIR/safety_$TIMESTAMP.json" 2>/dev/null; then
    echo -e "${GREEN}✓ Safety scan completed - No vulnerabilities found${NC}"
else
    echo -e "${YELLOW}⚠ Safety found vulnerabilities - Check $REPORT_DIR/safety_$TIMESTAMP.json${NC}"
    echo "Note: Some vulnerabilities may be false positives or have mitigations"
fi
echo ""

# Run pip-audit
echo "4. Running pip-audit..."
echo "=================================="
echo "Auditing installed packages..."
echo ""

if pip-audit --desc --format json --output "$REPORT_DIR/pip_audit_$TIMESTAMP.json"; then
    echo -e "${GREEN}✓ pip-audit completed - No vulnerabilities found${NC}"
else
    echo -e "${YELLOW}⚠ pip-audit found vulnerabilities - Check $REPORT_DIR/pip_audit_$TIMESTAMP.json${NC}"
fi
echo ""

# Check for secrets in code
echo "5. Checking for exposed secrets..."
echo "=================================="
echo "Scanning for accidentally committed secrets..."
echo ""

SECRETS_FOUND=0

# Check for common secret patterns
if grep -r "api_key.*=.*['\"][^'\"]*['\"]" src/ --include="*.py" | grep -v "test" | grep -v "example"; then
    echo -e "${RED}✗ Potential API keys found in code${NC}"
    SECRETS_FOUND=1
fi

if grep -r "secret.*=.*['\"][^'\"]*['\"]" src/ --include="*.py" | grep -v "test" | grep -v "example"; then
    echo -e "${RED}✗ Potential secrets found in code${NC}"
    SECRETS_FOUND=1
fi

if grep -r "password.*=.*['\"][^'\"]*['\"]" src/ --include="*.py" | grep -v "test" | grep -v "example"; then
    echo -e "${RED}✗ Potential passwords found in code${NC}"
    SECRETS_FOUND=1
fi

if [ $SECRETS_FOUND -eq 0 ]; then
    echo -e "${GREEN}✓ No exposed secrets found in code${NC}"
fi
echo ""

# Check .env file is not committed
echo "6. Checking .gitignore configuration..."
echo "=================================="

if grep -q "^\.env$" .gitignore; then
    echo -e "${GREEN}✓ .env file is properly ignored${NC}"
else
    echo -e "${RED}✗ .env file is not in .gitignore${NC}"
fi

if grep -q "credentials" .gitignore; then
    echo -e "${GREEN}✓ credentials files are ignored${NC}"
else
    echo -e "${YELLOW}⚠ credentials pattern not in .gitignore${NC}"
fi
echo ""

# Check file permissions
echo "7. Checking file permissions..."
echo "=================================="

if [ -f ".env" ]; then
    PERMS=$(stat -c "%a" .env)
    if [ "$PERMS" = "600" ] || [ "$PERMS" = "400" ]; then
        echo -e "${GREEN}✓ .env file has secure permissions ($PERMS)${NC}"
    else
        echo -e "${YELLOW}⚠ .env file permissions should be 600 (current: $PERMS)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ .env file not found${NC}"
fi
echo ""

# Check for outdated dependencies
echo "8. Checking for outdated dependencies..."
echo "=================================="

pip list --outdated --format=json > "$REPORT_DIR/outdated_$TIMESTAMP.json"
OUTDATED_COUNT=$(cat "$REPORT_DIR/outdated_$TIMESTAMP.json" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))")

if [ "$OUTDATED_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠ $OUTDATED_COUNT packages are outdated${NC}"
    echo "Check $REPORT_DIR/outdated_$TIMESTAMP.json for details"
else
    echo -e "${GREEN}✓ All packages are up to date${NC}"
fi
echo ""

# Check Docker security (if applicable)
echo "9. Checking Docker security..."
echo "=================================="

if command -v docker &> /dev/null; then
    # Check if running containers as root
    if docker ps --format '{{.Names}}' | xargs -I {} docker inspect {} --format='{{.Config.User}}' | grep -q "^$"; then
        echo -e "${YELLOW}⚠ Some containers running as root${NC}"
    else
        echo -e "${GREEN}✓ Containers not running as root${NC}"
    fi
else
    echo "Docker not installed - skipping"
fi
echo ""

# Summary
echo "=================================="
echo "Security Audit Summary"
echo "=================================="
echo ""
echo "Reports generated:"
echo "  - Full report: $REPORT_FILE"
echo "  - Bandit: $REPORT_DIR/bandit_$TIMESTAMP.txt"
echo "  - Safety: $REPORT_DIR/safety_$TIMESTAMP.json"
echo "  - pip-audit: $REPORT_DIR/pip_audit_$TIMESTAMP.json"
echo "  - Outdated packages: $REPORT_DIR/outdated_$TIMESTAMP.json"
echo ""
echo "Recommendations:"
echo "  1. Review all findings in the reports"
echo "  2. Update outdated packages: pip install -U <package>"
echo "  3. Fix any critical security issues immediately"
echo "  4. Run 'make security-audit' regularly"
echo "  5. Enable pre-commit hooks: pre-commit install"
echo ""
echo "For production deployment:"
echo "  - Use read-only API keys"
echo "  - Enable IP whitelisting on exchanges"
echo "  - Use secrets manager (AWS Secrets Manager, Vault)"
echo "  - Enable firewall (ufw/iptables)"
echo "  - Set up SSL/TLS for web interfaces"
echo ""
echo "Audit completed at: $(date)"
