# Security Policy

## Overview

This document outlines security best practices and guidelines for the Crypto Research Platform. As this platform handles sensitive financial data and API credentials, security must be a top priority.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**DO NOT** create public GitHub issues for security vulnerabilities.

Instead, please report security issues privately:

1. Email: security@yourdomain.com (replace with actual contact)
2. Use GitHub's private vulnerability reporting feature
3. Encrypt sensitive details using our PGP key (if available)

You should receive a response within 48 hours. If the issue is confirmed, we will:
- Release a patch as soon as possible
- Credit you in the security advisory (if desired)
- Notify users of affected versions

## Security Best Practices

### 1. API Key Management

#### Never Commit Secrets

**CRITICAL:** Never commit API keys, secrets, or credentials to version control.

```bash
# Verify .gitignore includes:
.env
.env.local
.env.*.local
*.key
*.pem
credentials.json
secrets/
```

#### Use Environment Variables

Store all credentials in environment variables:

```bash
# .env file (NEVER commit this)
BINANCE_API_KEY=your_key_here
BINANCE_SECRET=your_secret_here
COINBASE_API_KEY=your_key_here
COINBASE_SECRET=your_secret_here
```

#### Use Read-Only API Keys

When possible, use read-only or restricted API keys:

**Binance:**
- Enable "Enable Reading" only
- Disable "Enable Spot & Margin Trading"
- Enable IP whitelist restrictions

**Coinbase:**
- Select "View" permissions only
- Enable IP whitelist

#### API Key Rotation

Rotate API keys regularly:

```bash
# Set rotation schedule in configs/production.yaml
security:
  api_keys:
    rotation_days: 90
```

Automated rotation script:
```bash
python scripts/rotate_api_keys.py --exchange binance --notify
```

### 2. Secrets Management

#### For Production: Use Secrets Manager

**AWS Secrets Manager:**
```python
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name):
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager')

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except ClientError as e:
        raise e
```

**HashiCorp Vault:**
```python
import hvac

client = hvac.Client(url='http://localhost:8200')
client.token = 'your-token'

secret = client.secrets.kv.v2.read_secret_version(
    path='crypto-research/binance'
)
api_key = secret['data']['data']['api_key']
```

#### For Development: Use .env Files

```bash
# Install python-dotenv
pip install python-dotenv

# Load in application
from dotenv import load_dotenv
load_dotenv()
```

### 3. Network Security

#### Firewall Configuration

**UFW (Ubuntu):**
```bash
# Default deny
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (change 22 to custom port)
sudo ufw allow 22/tcp

# Allow HTTPS (if using web interface)
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
```

#### IP Whitelisting

Whitelist your server's IP on exchange APIs:

1. **Binance:** API Management → Edit Restrictions → Restrict access to trusted IPs
2. **Coinbase:** API Settings → IP Whitelist

#### TLS/SSL

Always use HTTPS for web interfaces:

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d crypto.yourdomain.com

# Auto-renewal
sudo systemctl enable certbot.timer
```

### 4. Database Security

#### Encryption at Rest

Enable encryption for sensitive data:

```sql
-- In DuckDB (if supported)
PRAGMA enable_encryption=true;
```

For Parquet files, use encrypted file systems:
```bash
# LUKS encryption on Linux
sudo cryptsetup luksFormat /dev/sdX
sudo cryptsetup open /dev/sdX crypto_data
```

#### Access Control

```bash
# Restrict database file permissions
chmod 600 /var/lib/crypto-research/data/crypto.duckdb
chown crypto-research:crypto-research /var/lib/crypto-research/data/crypto.duckdb
```

#### Backup Encryption

Encrypt backups before storing:

```bash
# Using GPG
tar -czf - /var/lib/crypto-research/data | \
    gpg --symmetric --cipher-algo AES256 \
    > backup-$(date +%Y%m%d).tar.gz.gpg

# Decrypt
gpg --decrypt backup-20240101.tar.gz.gpg | tar -xzf -
```

### 5. Application Security

#### Input Validation

Always validate and sanitize user inputs:

```python
from pydantic import BaseModel, validator

class SymbolRequest(BaseModel):
    symbol: str
    exchange: str

    @validator('symbol')
    def validate_symbol(cls, v):
        # Only allow alphanumeric and /
        if not re.match(r'^[A-Z0-9/]+$', v):
            raise ValueError('Invalid symbol format')
        return v
```

#### SQL Injection Prevention

Use parameterized queries:

```python
# GOOD - Parameterized
db.execute(
    "SELECT * FROM ohlcv WHERE symbol = ? AND exchange = ?",
    (symbol, exchange)
)

# BAD - String concatenation
db.execute(f"SELECT * FROM ohlcv WHERE symbol = '{symbol}'")
```

#### Rate Limiting

Implement rate limiting to prevent abuse:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.route("/api/data")
@limiter.limit("10 per minute")
def get_data():
    return {"data": "..."}
```

### 6. Authentication & Authorization

#### Streamlit Authentication

Add authentication to Streamlit UI:

```python
# config.toml
[server]
enableCORS = false
enableXsrfProtection = true

# In app.py
import streamlit_authenticator as stauth

authenticator = stauth.Authenticate(
    credentials,
    'crypto_research',
    'secret_key',
    30  # expiry days
)

name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status:
    # Show app
    pass
elif authentication_status == False:
    st.error('Username/password is incorrect')
```

#### API Key Authentication

For API endpoints:

```python
from functools import wraps
import secrets

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != os.getenv('INTERNAL_API_KEY'):
            return {"error": "Invalid API key"}, 401
        return f(*args, **kwargs)
    return decorated_function

@app.route("/api/backtest")
@require_api_key
def run_backtest():
    pass
```

### 7. Dependency Security

#### Regular Updates

Keep dependencies updated:

```bash
# Check for security vulnerabilities
pip-audit

# Update packages
pip install --upgrade pip
pip install --upgrade -r requirements.txt
```

#### Automated Scanning

Use automated tools:

```bash
# Bandit - Python code security
bandit -r src/

# Safety - Dependency vulnerabilities
safety check

# Pip-audit
pip-audit --desc
```

#### Pin Dependencies

Use version constraints in `pyproject.toml`:

```toml
dependencies = [
    "ccxt>=4.0.0,<5.0.0",  # Prevents breaking changes
    "pandas>=2.0.0,<3.0.0",
]
```

### 8. Logging & Monitoring

#### Secure Logging

**Never log sensitive data:**

```python
# BAD
logger.info(f"API Key: {api_key}")

# GOOD
logger.info("API authentication successful")
```

**Sanitize logs:**

```python
import logging

class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        # Redact API keys
        record.msg = re.sub(
            r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\']+)',
            r'\1***REDACTED***',
            str(record.msg)
        )
        return True

logger.addFilter(SensitiveDataFilter())
```

#### Intrusion Detection

Monitor for suspicious activity:

```bash
# Install fail2ban
sudo apt install fail2ban

# Configure for SSH
sudo nano /etc/fail2ban/jail.local
```

```ini
[sshd]
enabled = true
port = 22
maxretry = 3
bantime = 3600
```

#### Log Monitoring

Use centralized logging:

```bash
# Install and configure rsyslog
sudo apt install rsyslog

# Forward to central server
*.* @@logserver.example.com:514
```

### 9. Code Security

#### Pre-commit Hooks

Use security checks in pre-commit:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.6
    hooks:
      - id: bandit
        args: ['-ll']

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: detect-private-key
```

#### Code Review

Security checklist for code reviews:
- [ ] No hardcoded credentials
- [ ] Input validation present
- [ ] SQL queries parameterized
- [ ] Error messages don't leak sensitive info
- [ ] Dependencies are trusted
- [ ] Encryption used for sensitive data

### 10. Incident Response

#### Security Incident Procedure

1. **Identify:** Detect and confirm the incident
2. **Contain:** Isolate affected systems
3. **Eradicate:** Remove the threat
4. **Recover:** Restore systems
5. **Learn:** Document and improve

#### Emergency Contacts

Maintain updated contact list:
- System administrator
- Security team
- Exchange support
- Legal team (if required)

#### Incident Response Plan

```bash
# Stop services immediately
sudo systemctl stop crypto-research crypto-research-collector

# Revoke API keys
python scripts/revoke_api_keys.py --all --emergency

# Backup current state for forensics
sudo tar -czf incident-$(date +%Y%m%d-%H%M%S).tar.gz \
    /var/lib/crypto-research/ /var/log/crypto-research/

# Reset credentials
python scripts/rotate_api_keys.py --force --notify
```

## Security Checklist

### Development
- [ ] .env file in .gitignore
- [ ] No credentials in code
- [ ] Pre-commit hooks enabled
- [ ] Dependencies scanned
- [ ] Code reviewed

### Deployment
- [ ] Firewall configured
- [ ] SSH key-only authentication
- [ ] API keys use read-only permissions
- [ ] IP whitelist enabled on exchanges
- [ ] TLS/SSL configured
- [ ] Database encrypted
- [ ] Backups encrypted
- [ ] Logs monitored
- [ ] Fail2ban configured
- [ ] Security updates automated

### Operation
- [ ] API keys rotated (< 90 days old)
- [ ] Dependencies updated weekly
- [ ] Security scans run daily
- [ ] Logs reviewed regularly
- [ ] Backups tested monthly
- [ ] Incident response plan tested

## Compliance

### Data Privacy

This platform may process:
- Financial data
- API credentials
- Trading history

Ensure compliance with:
- GDPR (if handling EU data)
- Local financial regulations
- Exchange terms of service

### Audit Trail

Maintain audit logs:

```python
import logging

audit_logger = logging.getLogger('audit')

def log_trade(user, symbol, amount, price):
    audit_logger.info(
        f"Trade executed: user={user} symbol={symbol} "
        f"amount={amount} price={price}"
    )
```

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [Exchange Security Guides](https://www.binance.com/en/support/faq/security)

## Contact

For security concerns:
- Email: security@yourdomain.com
- PGP Key: [fingerprint]
- Response time: 48 hours

---

**Remember:** Security is not a one-time setup but an ongoing process. Regular reviews and updates are essential.
