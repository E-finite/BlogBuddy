# DEPLOYMENT — Blogbot SaaS Agent

> **Complete Productie Tutorial**
> Ubuntu 22.04 LTS · Flask 3.0 · MySQL · Gunicorn · Nginx · phpMyAdmin · Fail2ban · SSL

---

## Architectuuroverzicht

```
Internet
  |
  v
[Fail2ban — blokkeer aanvallen]
  |
  v
[UFW Firewall — alleen 22/80/443]
  |
  v
[Nginx — poort 443 HTTPS + SSL]
  |-- /         --> Gunicorn socket --> Flask Agent
  |-- /static   --> Statische bestanden (direct)
  |-- /beheer   --> PHP-FPM --> phpMyAdmin
              |
              v
         [MySQL 8.0]
          blogbot_db
```

---

## Vereisten

| Component | Minimaal |
|-----------|----------|
| OS        | Ubuntu 22.04 LTS |
| Python    | 3.9 of hoger |
| MySQL     | 8.0 (meegeleverd via apt) |
| RAM       | 1 GB minimum, 2 GB aanbevolen |
| CPU       | 1 vCPU minimum, 2 aanbevolen |
| Opslag    | 10 GB SSD minimum |
| Netwerk   | Vaste publieke IP of domeinnaam |

---

## Benodigde `.env` variabelen

| Variabele              | Verplicht | Doel |
|------------------------|-----------|------|
| `OPENAI_API_KEY`       | Ja        | Tekstgeneratie via OpenAI |
| `GEMINI_API_KEY`       | Ja        | Afbeeldingsgeneratie via Gemini |
| `MASTER_KEY`           | Ja        | Encryptie (min. 32 tekens) |
| `MYSQL_HOST`           | Ja        | Database host (localhost) |
| `MYSQL_PORT`           | Ja        | Standaard 3306 |
| `MYSQL_USER`           | Ja        | DB gebruiker |
| `MYSQL_PASSWORD`       | Ja        | DB wachtwoord |
| `MYSQL_DATABASE`       | Ja        | DB naam |
| `APP_HOST`             | Ja        | 0.0.0.0 |
| `APP_PORT`             | Ja        | Standaard 8000 |
| `APP_PUBLIC_URL`       | Ja        | Publieke URL (voor wachtwoord reset links) |
| `MAIL_SERVER`          | Ja\*      | SMTP server (\*voor wachtwoordreset) |
| `MAIL_PORT`            | Ja\*      | Standaard 587 |
| `MAIL_USERNAME`        | Ja\*      | SMTP gebruiker |
| `MAIL_PASSWORD`        | Ja\*      | SMTP wachtwoord |
| `MAIL_DEFAULT_SENDER`  | Ja\*      | Afzenderadres |
| `ADMIN_EMAILS`         | Nee       | Kommagescheiden lijst van admin e-mails |

---

## Fase 1 — Server voorbereiden

### Stap 1 — Inloggen en updaten

```bash
ssh root@JOUW_SERVER_IP
apt update && apt upgrade -y
reboot
```

### Stap 2 — Alle software installeren

```bash
apt install -y \
    python3 python3-pip python3-venv python3-dev \
    build-essential \
    mysql-server \
    nginx \
    php8.1 php8.1-fpm php8.1-mysql \
    php8.1-mbstring php8.1-zip php8.1-gd \
    php8.1-json php8.1-curl \
    certbot python3-certbot-nginx \
    fail2ban git curl unzip ufw logrotate
```

### Stap 3 — Aparte gebruiker aanmaken

```bash
adduser flaskuser
usermod -aG sudo flaskuser
usermod -aG www-data flaskuser
```

### Stap 4 — Firewall instellen (**VERPLICHT**)

> Alleen poort 22 (SSH), 80 (HTTP) en 443 (HTTPS) openen. Poort 8000 en 3306 blijven **GESLOTEN** van buitenaf!

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status verbose
```

---

## Fase 2 — MySQL instellen

### Stap 5 — MySQL beveiligen

```bash
mysql_secure_installation
```

| Vraag | Antwoord |
|-------|----------|
| Validate password?          | N |
| Remove anonymous users?     | Y |
| Disallow root login remotely? | Y |
| Remove test database?       | Y |
| Reload privileges?          | Y |

### Stap 6 — Database en gebruiker aanmaken

> **NOOIT root gebruiken — altijd een aparte gebruiker met beperkte rechten!**

```bash
mysql -u root -p
```

```sql
CREATE DATABASE blogbot_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'blogbot_user'@'localhost' IDENTIFIED BY 'SterkWachtwoord123!';
GRANT ALL PRIVILEGES ON blogbot_db.* TO 'blogbot_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### Stap 7 — MySQL verbinding testen

```bash
mysql -u blogbot_user -p blogbot_db
```

Zie je de MySQL-prompt? Dan werkt het. Typ `EXIT;` om te verlaten.

---

## Fase 3 — Flask app deployen

### Stap 8 — Projectmap aanmaken

```bash
mkdir -p /var/www/blogbot
chown flaskuser:www-data /var/www/blogbot
chmod 750 /var/www/blogbot
```

### Stap 9 — Code uploaden

**Via Git:**

```bash
su - flaskuser
cd /var/www/blogbot
git clone https://github.com/jouw-gebruiker/jouw-repo.git .
```

**Via SCP (vanuit lokale machine):**

```bash
scp -r ./jouw_project flaskuser@JOUW_SERVER_IP:/var/www/blogbot/
```

### Stap 10 — Virtual environment aanmaken

```bash
cd /var/www/blogbot
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### Stap 11 — `.env` bestand aanmaken

```bash
nano /var/www/blogbot/.env
```

```env
# AI API Keys
OPENAI_API_KEY=sk-jouw-openai-sleutel-hier
GEMINI_API_KEY=jouw-gemini-sleutel-hier

# Encryptie (minimaal 32 tekens!)
MASTER_KEY=VulHierEenSterkeMasterKeyIn12345!

# Database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=blogbot_user
MYSQL_PASSWORD=SterkWachtwoord123!
MYSQL_DATABASE=blogbot_db

# App
APP_HOST=0.0.0.0
APP_PORT=8000
APP_PUBLIC_URL=https://jouwdomein.nl

# E-mail (SMTP)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=jouw@gmail.com
MAIL_PASSWORD=jouw-app-wachtwoord
MAIL_DEFAULT_SENDER=jouw@gmail.com

# Admins (optioneel)
ADMIN_EMAILS=admin@jouwdomein.nl
```

Daarna beveiliging toepassen:

```bash
chmod 600 /var/www/blogbot/.env
chown flaskuser:flaskuser /var/www/blogbot/.env
```

### Stap 12 — WSGI bestand aanmaken

```bash
nano /var/www/blogbot/wsgi.py
```

```python
from app import app
if __name__ == '__main__':
    app.run()
```

### Stap 13 — Gunicorn configuratiebestand

```bash
nano /var/www/blogbot/gunicorn.conf.py
```

```python
import multiprocessing
workers = multiprocessing.cpu_count() * 2 + 1
bind = "unix:/var/www/blogbot/blogbot.sock"
timeout = 300
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
accesslog = "/var/log/blogbot/access.log"
errorlog = "/var/log/blogbot/error.log"
loglevel = "info"
preload_app = True
```

Log map aanmaken:

```bash
mkdir -p /var/log/blogbot
chown flaskuser:flaskuser /var/log/blogbot
```

### Stap 14 — Systemd service aanmaken

```bash
nano /etc/systemd/system/blogbot.service
```

```ini
[Unit]
Description=Gunicorn service voor Blogbot SaaS Agent
After=network.target mysql.service
Wants=mysql.service

[Service]
User=flaskuser
Group=www-data
WorkingDirectory=/var/www/blogbot
EnvironmentFile=/var/www/blogbot/.env
Environment="PATH=/var/www/blogbot/venv/bin"
ExecStart=/var/www/blogbot/venv/bin/gunicorn --config /var/www/blogbot/gunicorn.conf.py wsgi:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Service starten:

```bash
systemctl daemon-reload
systemctl start blogbot
systemctl enable blogbot
systemctl status blogbot
```

---

## Fase 4 — phpMyAdmin installeren

### Stap 15 — PHP-FPM starten

```bash
systemctl start php8.1-fpm
systemctl enable php8.1-fpm
```

### Stap 16 — phpMyAdmin downloaden

```bash
cd /tmp
wget https://www.phpmyadmin.net/downloads/phpMyAdmin-latest-all-languages.tar.gz
tar -xzf phpMyAdmin-latest-all-languages.tar.gz
mv phpMyAdmin-*-all-languages /usr/share/phpmyadmin
mkdir -p /usr/share/phpmyadmin/tmp
chmod 777 /usr/share/phpmyadmin/tmp
chown -R www-data:www-data /usr/share/phpmyadmin
```

### Stap 17 — phpMyAdmin configureren

```bash
cp /usr/share/phpmyadmin/config.sample.inc.php /usr/share/phpmyadmin/config.inc.php
```

Genereer een veilige blowfish secret met:

```bash
openssl rand -base64 32
```

Vul in `config.inc.php` in:

```php
$cfg['blowfish_secret'] = 'PLAK_HIER_DE_GEGENEREERDE_STRING';
```

---

## Fase 5 — Nginx configureren

### Stap 18 — Nginx configuratiebestand aanmaken

```bash
nano /etc/nginx/sites-available/blogbot
```

```nginx
# Rate limiting (bescherming tegen bots)
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

server {
    listen 80;
    server_name jouwdomein.nl www.jouwdomein.nl;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name jouwdomein.nl www.jouwdomein.nl;

    # SSL (Certbot vult dit automatisch in)

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    server_tokens off;
    client_max_body_size 10M;

    # Flask App
    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/blogbot/blogbot.sock;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        limit_req zone=api burst=20 nodelay;
    }

    # Statische bestanden
    location /static {
        alias /var/www/blogbot/static;
        expires 30d;
    }

    # phpMyAdmin — geheime URL, beperkt tot jouw IP!
    location /beheer {
        alias /usr/share/phpmyadmin;
        index index.php;
        allow JOUW_THUIS_IP;
        deny all;
        location ~ \.php$ {
            fastcgi_pass unix:/run/php/php8.1-fpm.sock;
            fastcgi_index index.php;
            fastcgi_param SCRIPT_FILENAME $request_filename;
            include fastcgi_params;
        }
    }

    # Blokkeer gevaarlijke paden
    location ~ /\. { deny all; }
    location ~ /\.env { deny all; }
}
```

Nginx activeren:

```bash
rm /etc/nginx/sites-enabled/default
ln -s /etc/nginx/sites-available/blogbot /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

---

## Fase 6 — SSL certificaat

### Stap 19 — DNS instellen

| Type | Naam | Waarde |
|------|------|--------|
| A    | @    | JOUW_SERVER_IP |
| A    | www  | JOUW_SERVER_IP |

> Wacht 5 tot 30 minuten totdat DNS is doorgezet.

### Stap 20 — SSL installeren via Certbot

```bash
certbot --nginx -d jouwdomein.nl -d www.jouwdomein.nl --email jouw@email.nl --agree-tos --no-eff-email
```

Automatische verlenging testen:

```bash
certbot renew --dry-run
```

---

## Fase 7 — Fail2ban instellen

### Stap 21 — Fail2ban configureren

```bash
nano /etc/fail2ban/jail.local
```

```ini
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5
backend  = systemd

[sshd]
enabled = true

[nginx-http-auth]
enabled = true

[nginx-limit-req]
enabled  = true
filter   = nginx-limit-req
logpath  = /var/log/nginx/error.log
maxretry = 10
```

Fail2ban starten:

```bash
systemctl restart fail2ban
systemctl enable fail2ban
```

---

## Fase 8 — Automatische updates

### Stap 22 — Automatische beveiligingsupdates

```bash
apt install unattended-upgrades -y
dpkg-reconfigure --priority=low unattended-upgrades
```

---

## Fase 9 — Logrotatie

### Stap 23 — Logs automatisch opruimen

```bash
nano /etc/logrotate.d/blogbot
```

```
/var/log/blogbot/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 flaskuser flaskuser
    postrotate
        systemctl reload blogbot
    endscript
}
```

---

## Fase 10 — Uitgaand verkeer testen

### Stap 24 — Externe verbindingen controleren

```bash
curl -I https://api.openai.com
curl -I https://generativelanguage.googleapis.com
nc -zv smtp.gmail.com 587
```

---

## Fase 11 — Database verbinding testen

### Stap 25 — Verbindingstest uitvoeren en verwijderen

```bash
su - flaskuser
cd /var/www/blogbot
source venv/bin/activate
nano test_db.py
```

```python
import mysql.connector
from dotenv import load_dotenv
import os
load_dotenv()
try:
    conn = mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        port=int(os.getenv('MYSQL_PORT')),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE')
    )
    print('MySQL verbinding succesvol!')
    conn.close()
except Exception as e:
    print(f'Fout: {e}')
```

```bash
python test_db.py
rm test_db.py   # VERWIJDER DIT BESTAND DAARNA ALTIJD!
```

---

## Fase 12 — Alles controleren

### Stap 26 — Services checken

```bash
systemctl status blogbot
systemctl status nginx
systemctl status mysql
systemctl status php8.1-fpm
systemctl status fail2ban
```

### Stap 27 — Testen in de browser

| Wat | URL |
|-----|-----|
| Flask Agent | https://jouwdomein.nl/ |
| phpMyAdmin  | https://jouwdomein.nl/beheer |

---

## Dagelijkse beheercommando's

**App updaten na code-wijziging:**

```bash
cd /var/www/blogbot
git pull
source venv/bin/activate
pip install -r requirements.txt
systemctl restart blogbot
```

**Logs bekijken:**

```bash
journalctl -u blogbot -f
tail -f /var/log/blogbot/error.log
tail -f /var/log/nginx/error.log
```

**Database backup:**

```bash
mysqldump -u blogbot_user -p blogbot_db > ~/backup_$(date +%Y%m%d_%H%M).sql
```

**Fail2ban status:**

```bash
fail2ban-client status
fail2ban-client status sshd
```

**Schijf- en geheugengebruik:**

```bash
df -h
free -h
```

---

## Definitief stackoverzicht

| Component       | Tool                        | Status      |
|-----------------|-----------------------------|-------------|
| OS              | Ubuntu 22.04 LTS            | Vereist     |
| Python          | 3.10 (minimaal 3.9)         | Vereist     |
| App server      | Flask 3.0 + Gunicorn        | Vereist     |
| DB connectie    | mysql-connector-python      | Vereist     |
| Database        | MySQL 8.0                   | Vereist     |
| DB beheer       | phpMyAdmin                  | Aanbevolen  |
| Webserver       | Nginx + security headers    | Vereist     |
| SSL             | Let's Encrypt via Certbot   | Vereist     |
| Procesmanager   | systemd (auto-restart)      | Vereist     |
| Firewall        | UFW (alleen 22/80/443)      | Vereist     |
| Aanvalsbescherming | Fail2ban                 | Vereist     |
| Rate limiting   | Nginx limit_req             | Vereist     |
| Logs            | Logrotate (14 dagen)        | Aanbevolen  |
| Updates         | Unattended-upgrades         | Aanbevolen  |

---

> **BELANGRIJK: ZET `.env` NOOIT IN JE GIT REPOSITORY!**
>
> Voeg `.env` toe aan je `.gitignore`:
>
> ```bash
> echo '.env' >> .gitignore
> ```

---

*Dit bestand is gegenereerd door DAAN — De AI-Assistent van de Provincie Noord-Holland*
