# Deployment Guide — AcadResult System
## Local → Staging → Production

---

## PHASE 1 — Local Development Setup

### Step 1: Clone and install
```bash
git clone https://github.com/youruser/acadresult.git
cd acadresult/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate          # Mac/Linux
venv\Scripts\activate             # Windows

pip install -r requirements.txt
```

### Step 2: Configure environment
```bash
cp ../config/.env.example .env
# Open .env and set:
#   SECRET_KEY=<random string>
#   FLASK_ENV=development
#   INSTITUTION_NAME=Your Institution
```

### Step 3: Initialize database
```bash
flask db init
flask db migrate -m "initial migration"
flask db upgrade
```

### Step 4: Generate AI training data and train model
```bash
# Generate dataset
python ../ai_module/data/generate_dataset.py

# Train model (saves to ai_module/models/performance_model.pkl)
python app/ai/train.py
```

### Step 5: Seed database with sample data
```bash
python ../scripts/seed_db.py
```

### Step 6: Run development server
```bash
python run.py
# Open: http://localhost:5000
```

### Step 7: Run tests
```bash
pytest tests/ -v
```

---

## PHASE 2 — Production Deployment (DigitalOcean / Ubuntu)

### Prerequisites
- Ubuntu 22.04 VPS (minimum 1GB RAM)
- Domain name pointed to your server IP
- SSH access as root or sudo user

---

### Step 1: Server setup
```bash
# Connect to your server
ssh root@YOUR_SERVER_IP

# Update system
apt update && apt upgrade -y

# Install Python, PostgreSQL, Nginx
apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx git

# Create a system user for the app
useradd -m -s /bin/bash acadresult
su - acadresult
```

### Step 2: PostgreSQL database setup
```bash
# Switch to postgres user
sudo -u postgres psql

-- Inside psql:
CREATE DATABASE acadresult_db;
CREATE USER acadresult_user WITH ENCRYPTED PASSWORD 'StrongPassword123!';
GRANT ALL PRIVILEGES ON DATABASE acadresult_db TO acadresult_user;
\q
```

### Step 3: Deploy application code
```bash
# As acadresult user
cd /home/acadresult
git clone https://github.com/youruser/acadresult.git
cd acadresult/backend

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 4: Production .env
```bash
nano .env
```
```
FLASK_ENV=production
SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=postgresql://acadresult_user:StrongPassword123!@localhost:5432/acadresult_db
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=youremail@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_DEFAULT_SENDER=noreply@yourinstitution.edu.ng
INSTITUTION_NAME=Federal Polytechnic Ede
PORTAL_URL=https://results.yourinstitution.edu.ng
```

### Step 5: Initialize production database
```bash
flask db upgrade
python ../ai_module/data/generate_dataset.py
python app/ai/train.py
python ../scripts/seed_db.py
```

### Step 6: Create systemd service (keeps app running)
```bash
sudo nano /etc/systemd/system/acadresult.service
```
```ini
[Unit]
Description=AcadResult Gunicorn Service
After=network.target

[Service]
User=acadresult
Group=acadresult
WorkingDirectory=/home/acadresult/acadresult/backend
Environment="PATH=/home/acadresult/acadresult/backend/venv/bin"
EnvironmentFile=/home/acadresult/acadresult/backend/.env
ExecStart=/home/acadresult/acadresult/backend/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/home/acadresult/acadresult.sock \
    --access-logfile /var/log/acadresult/access.log \
    --error-logfile /var/log/acadresult/error.log \
    run:app

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```bash
sudo mkdir -p /var/log/acadresult
sudo chown acadresult:acadresult /var/log/acadresult
sudo systemctl daemon-reload
sudo systemctl enable acadresult
sudo systemctl start acadresult
sudo systemctl status acadresult   # Should show: active (running)
```

### Step 7: Nginx configuration
```bash
sudo nano /etc/nginx/sites-available/acadresult
```
```nginx
server {
    listen 80;
    server_name results.yourinstitution.edu.ng;

    # Redirect HTTP → HTTPS (after SSL setup)
    # return 301 https://$host$request_uri;

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/acadresult/acadresult.sock;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /home/acadresult/acadresult/frontend/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    client_max_body_size 10M;
}
```
```bash
sudo ln -s /etc/nginx/sites-available/acadresult /etc/nginx/sites-enabled/
sudo nginx -t        # Test config
sudo systemctl reload nginx
```

### Step 8: SSL Certificate (HTTPS) with Let's Encrypt
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d results.yourinstitution.edu.ng
# Follow prompts — certbot auto-renews every 90 days
```

---

## PHASE 3 — Alternative: Deploy on Render.com (Free/Easy)

Render is easier than a VPS and has a free tier.

1. Push code to GitHub
2. Go to https://render.com → New → Web Service
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r backend/requirements.txt`
   - **Start Command:** `cd backend && gunicorn run:app`
   - **Root Directory:** (leave blank)
5. Add all environment variables from .env.example
6. Add a **PostgreSQL** database from Render dashboard
7. Copy the `DATABASE_URL` from Render PostgreSQL into env vars
8. Deploy — Render handles SSL automatically

---

## PHASE 4 — Alternative: Railway.app (One-click)

```bash
npm install -g @railway/cli
railway login
railway init
railway up
railway vars set SECRET_KEY=xxx DATABASE_URL=xxx ...
```

---

## Backup & Recovery

### Automated database backup (PostgreSQL)
```bash
# Add to crontab: crontab -e
# Run every day at 2 AM
0 2 * * * pg_dump -U acadresult_user acadresult_db | gzip > /backups/acadresult_$(date +\%Y\%m\%d).sql.gz
```

### Restore from backup
```bash
gunzip -c /backups/acadresult_20250101.sql.gz | psql -U acadresult_user acadresult_db
```

---

## Monitoring

### Check service status
```bash
sudo systemctl status acadresult
sudo journalctl -u acadresult -f    # Live logs
```

### Check Nginx logs
```bash
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/acadresult/error.log
```

---

## Retraining the AI Model (Quarterly)

```bash
cd /home/acadresult/acadresult/backend
source venv/bin/activate
python app/ai/train.py      # Re-trains on latest data
sudo systemctl restart acadresult
```
