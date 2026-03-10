# 🚀 Vison — Hosting & Deployment Guide

Complete guide for deploying Vison to production across multiple platforms.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Docker Compose (Self-Hosted VPS)](#1-docker-compose-self-hosted-vps)
3. [AWS (EC2 + Docker)](#2-aws-ec2--docker)
4. [Google Cloud (Cloud Run)](#3-google-cloud-cloud-run)
5. [Microsoft Azure (App Service)](#4-microsoft-azure-app-service)
6. [Railway (PaaS — Easiest)](#5-railway-paas)
7. [Render](#6-render)
8. [DigitalOcean App Platform](#7-digitalocean-app-platform)
9. [Environment Variables](#environment-variables)
10. [SSL & Domain Setup](#ssl--domain-setup)
11. [Production Hardening](#production-hardening)
12. [Monitoring & Logs](#monitoring--logs)
13. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before deploying, ensure you have:

- **Docker** and **Docker Compose** installed (for containerized deployments)
- **Git** for source control
- A **domain name** (optional but recommended)
- A **cloud account** on your chosen platform

### Build Checklist

```bash
# Clone or navigate to your project
cd vison/

# Verify project structure
ls backend/    # Should contain app/, requirements.txt, Dockerfile
ls frontend/   # Should contain server.js, package.json, Dockerfile
ls docker-compose.yml
```

---

## 1. Docker Compose (Self-Hosted VPS)

> **Best for:** Full control, any Linux VPS (Hetzner, Contabo, OVH, Linode, etc.)  
> **Cost:** $5–20/month for a basic VPS

### Step 1: Provision a VPS

Get a Linux server (Ubuntu 22.04+ recommended) with at least:
- **2 vCPUs**, **4 GB RAM** (for TensorFlow)
- **20 GB disk** (for media storage)

### Step 2: Install Docker

```bash
# SSH into your server
ssh root@your-server-ip

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
sudo apt-get install docker-compose-plugin

# Verify
docker --version
docker compose version
```

### Step 3: Deploy

```bash
# Clone your project to the server
git clone https://github.com/your-username/vison.git
cd vison

# Create production environment file
cat > .env << 'EOF'
DEBUG=false
USE_OPENVINO=true
CORS_ORIGINS=["https://yourdomain.com"]
EOF

# Build and start containers
docker compose up -d --build

# Verify services are running
docker compose ps
docker compose logs -f
```

### Step 4: Set up Nginx Reverse Proxy

```bash
sudo apt install nginx -y
```

Create `/etc/nginx/sites-available/vison`:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API (direct access)
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 100M;  # For large file uploads
    }

    # Static media files
    location /static/ {
        proxy_pass http://localhost:8000/static/;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/vison /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Step 5: SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
# Follow prompts, auto-renews via cron
```

---

## 2. AWS (EC2 + Docker)

> **Best for:** Scalable production deployments  
> **Cost:** ~$15-40/month (t3.medium recommended)

### Step 1: Launch EC2 Instance

1. Go to **AWS Console → EC2 → Launch Instance**
2. Choose **Ubuntu 22.04 LTS** AMI
3. Instance type: **t3.medium** (2 vCPU, 4 GB RAM) minimum
4. Storage: **30 GB gp3**
5. Security Group: Open ports **22** (SSH), **80** (HTTP), **443** (HTTPS)
6. Launch and download your key pair

### Step 2: Connect & Setup

```bash
# Connect
ssh -i your-key.pem ubuntu@your-ec2-public-ip

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
newgrp docker

# Install Docker Compose
sudo apt-get install docker-compose-plugin -y
```

### Step 3: Deploy

```bash
# Clone project
git clone https://github.com/your-username/vison.git
cd vison

# Deploy
docker compose up -d --build
```

### Step 4: (Optional) Use Elastic IP

1. AWS Console → EC2 → Elastic IPs → Allocate
2. Associate with your instance
3. Point your domain's A record to the Elastic IP

### Step 5: Set up Nginx + SSL

Follow the same Nginx + Certbot steps from the [VPS section](#step-4-set-up-nginx-reverse-proxy) above.

---

## 3. Google Cloud (Cloud Run)

> **Best for:** Serverless, auto-scaling, pay-per-use  
> **Cost:** Free tier available, ~$10-30/month under moderate use

### Step 1: Install gcloud CLI

```bash
# Download and install
curl https://sdk.cloud.google.com | bash
gcloud init
gcloud auth login
```

### Step 2: Set project

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com containerregistry.googleapis.com
```

### Step 3: Build & Push Docker Images

```bash
# Backend
cd backend
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/vison-backend
cd ..

# Frontend
cd frontend
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/vison-frontend
cd ..
```

### Step 4: Deploy Backend

```bash
gcloud run deploy vison-backend \
  --image gcr.io/YOUR_PROJECT_ID/vison-backend \
  --platform managed \
  --region us-central1 \
  --port 8000 \
  --memory 4Gi \
  --cpu 2 \
  --allow-unauthenticated \
  --set-env-vars "DEBUG=false,USE_OPENVINO=false"
```

> **Note:** Cloud Run is stateless. For persistent media storage, mount a **Cloud Storage bucket** via GCS FUSE or use an external database.

### Step 5: Deploy Frontend

```bash
# Get the backend URL from the previous deploy output
BACKEND_URL="https://vison-backend-xxxxx-uc.a.run.app"

gcloud run deploy vison-frontend \
  --image gcr.io/YOUR_PROJECT_ID/vison-frontend \
  --platform managed \
  --region us-central1 \
  --port 3000 \
  --memory 512Mi \
  --allow-unauthenticated \
  --set-env-vars "BACKEND_URL=$BACKEND_URL"
```

> [!IMPORTANT]
> Cloud Run is **stateless** — uploaded media and the FAISS index won't persist across container restarts. For production, add **Google Cloud Storage** for media and **Cloud SQL** for the database.

---

## 4. Microsoft Azure (App Service)

> **Best for:** Enterprise environments, Azure-native workflows  
> **Cost:** ~$15-50/month

### Step 1: Install Azure CLI

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az login
```

### Step 2: Create Resources

```bash
# Create resource group
az group create --name vison-rg --location eastus

# Create Azure Container Registry
az acr create --resource-group vison-rg --name visonregistry --sku Basic
az acr login --name visonregistry
```

### Step 3: Build & Push Images

```bash
# Backend
docker build -t visonregistry.azurecr.io/vison-backend:latest ./backend
docker push visonregistry.azurecr.io/vison-backend:latest

# Frontend
docker build -t visonregistry.azurecr.io/vison-frontend:latest ./frontend
docker push visonregistry.azurecr.io/vison-frontend:latest
```

### Step 4: Create App Service Plan & Deploy

```bash
# Create plan (B2 = 2 cores, 3.5 GB RAM)
az appservice plan create \
  --name vison-plan \
  --resource-group vison-rg \
  --sku B2 \
  --is-linux

# Deploy backend
az webapp create \
  --resource-group vison-rg \
  --plan vison-plan \
  --name vison-backend \
  --deployment-container-image-name visonregistry.azurecr.io/vison-backend:latest

# Configure backend
az webapp config appsettings set \
  --resource-group vison-rg \
  --name vison-backend \
  --settings DEBUG=false USE_OPENVINO=false WEBSITES_PORT=8000

# Deploy frontend
az webapp create \
  --resource-group vison-rg \
  --plan vison-plan \
  --name vison-frontend \
  --deployment-container-image-name visonregistry.azurecr.io/vison-frontend:latest

az webapp config appsettings set \
  --resource-group vison-rg \
  --name vison-frontend \
  --settings BACKEND_URL=https://vison-backend.azurewebsites.net WEBSITES_PORT=3000
```

---

## 5. Railway (PaaS)

> **Best for:** Quickest deployment, minimal DevOps  
> **Cost:** Free tier available, ~$5-20/month

### Step 1: Install Railway CLI

```bash
npm install -g @railway/cli
railway login
```

### Step 2: Deploy Backend

```bash
cd backend
railway init  # Name it "vison-backend"
railway up

# Set environment variables
railway variables set DEBUG=false
railway variables set USE_OPENVINO=false

# Get the deployed URL
railway open
```

### Step 3: Deploy Frontend

```bash
cd ../frontend
railway init  # Name it "vison-frontend"

# Set backend URL (from previous step)
railway variables set BACKEND_URL=https://vison-backend.up.railway.app
railway variables set PORT=3000

railway up
```

### Step 4: Add Custom Domain (Optional)

1. Go to Railway dashboard → your service → Settings → Domains
2. Add your custom domain
3. Update DNS records as instructed

---

## 6. Render

> **Best for:** GitHub-connected auto-deploy, free tier available  
> **Cost:** Free tier, ~$7-25/month for paid

### Step 1: Connect GitHub

1. Go to [render.com](https://render.com) and sign in with GitHub
2. Connect your Vison repository

### Step 2: Deploy Backend

1. **New → Web Service**
2. Connect your repo → Set:
   - **Name:** `vison-backend`
   - **Root Directory:** `backend`
   - **Runtime:** Docker
   - **Instance Type:** Standard (2 GB RAM minimum)
3. Add environment variables:
   - `DEBUG` = `false`
   - `USE_OPENVINO` = `false`
4. Click **Create Web Service**

### Step 3: Deploy Frontend

1. **New → Web Service**
2. Connect same repo → Set:
   - **Name:** `vison-frontend`
   - **Root Directory:** `frontend`
   - **Runtime:** Docker
   - **Instance Type:** Starter
3. Add environment variables:
   - `BACKEND_URL` = `https://vison-backend.onrender.com`
   - `PORT` = `3000`
4. Click **Create Web Service**

### Step 4: Add Persistent Disk (Backend)

1. Backend service → Settings → Disks
2. Add disk: **Mount Path** = `/app/data`, **Size** = 10 GB
3. This persists your media files and FAISS indices

---

## 7. DigitalOcean App Platform

> **Best for:** Simple PaaS with good pricing  
> **Cost:** ~$12-24/month

### Step 1: Create App

1. Go to [cloud.digitalocean.com](https://cloud.digitalocean.com) → App Platform → Create App
2. Connect your GitHub repository

### Step 2: Configure Components

Add two components from the same repo:

**Backend:**
- Source: `/backend`
- Type: Web Service
- Dockerfile Path: `backend/Dockerfile`
- HTTP Port: `8000`
- Instance: Basic (2 GB / 1 vCPU)
- Env vars: `DEBUG=false`, `USE_OPENVINO=false`

**Frontend:**
- Source: `/frontend`
- Type: Web Service
- Dockerfile Path: `frontend/Dockerfile`
- HTTP Port: `3000`
- Instance: Basic (512 MB)
- Env vars: `BACKEND_URL=${vison-backend.INTERNAL_URL}` (use internal routing), `PORT=3000`

### Step 3: Deploy

Click **Create Resources** — DigitalOcean builds and deploys both services.

---

## Environment Variables

Reference of all configurable environment variables:

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `DEBUG` | `true` | Enable debug logging | No |
| `HOST` | `0.0.0.0` | Backend bind address | No |
| `PORT` | `8000` (backend) / `3000` (frontend) | Server port | No |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins (JSON array) | **Yes** for prod |
| `USE_OPENVINO` | `true` | Intel OpenVINO acceleration | No |
| `BACKEND_URL` | `http://localhost:8000` | Backend URL (frontend only) | **Yes** for prod |
| `CRAWLER_MAX_DEPTH` | `3` | Max crawl depth | No |
| `CRAWLER_MAX_PAGES` | `100` | Max pages per crawl | No |
| `CRAWLER_DELAY_SECONDS` | `1.0` | Delay between crawled pages | No |

### Production `.env` Example

```env
# Backend
DEBUG=false
USE_OPENVINO=false
CORS_ORIGINS=["https://vison.yourdomain.com"]

# Frontend
BACKEND_URL=https://api.yourdomain.com
PORT=3000
```

---

## SSL & Domain Setup

### Option A: Certbot (VPS/EC2)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal is configured automatically
sudo certbot renew --dry-run
```

### Option B: Cloudflare (Any Platform)

1. Add your domain to [Cloudflare](https://cloudflare.com)
2. Update nameservers at your registrar
3. Set SSL mode to **Full (Strict)**
4. Cloudflare provides free SSL and CDN

### DNS Records

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | `@` | `your-server-ip` | 300 |
| A | `www` | `your-server-ip` | 300 |
| CNAME | `api` | `your-backend-url` | 300 |

---

## Production Hardening

### Security Checklist

```bash
# 1. Disable debug mode
DEBUG=false

# 2. Set specific CORS origins (not wildcard)
CORS_ORIGINS=["https://yourdomain.com"]

# 3. Set up firewall (VPS)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# 4. Keep Docker images updated
docker compose pull
docker compose up -d
```

### Performance Optimization

```nginx
# Add to Nginx for file upload optimization
client_max_body_size 100M;
proxy_read_timeout 300s;
proxy_connect_timeout 75s;

# Enable gzip
gzip on;
gzip_types text/plain text/css application/json application/javascript;
gzip_min_length 1000;
```

### Automatic Restarts

```bash
# Docker Compose already has restart: unless-stopped

# For extra reliability, add a systemd service
sudo tee /etc/systemd/system/vison.service << 'EOF'
[Unit]
Description=Vison Search Engine
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ubuntu/vison
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable vison
sudo systemctl start vison
```

### Backup Strategy

```bash
# Backup script — save to /home/ubuntu/backup-vison.sh
#!/bin/bash
BACKUP_DIR="/backups/vison/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup database
docker compose exec backend cp /app/data/vison.db /tmp/vison_backup.db
docker compose cp backend:/tmp/vison_backup.db "$BACKUP_DIR/vison.db"

# Backup FAISS indices
docker compose cp backend:/app/data/indices "$BACKUP_DIR/indices"

# Backup media (optional, can be large)
# docker compose cp backend:/app/data/media "$BACKUP_DIR/media"

echo "Backup completed: $BACKUP_DIR"

# Add to crontab: 0 3 * * * /home/ubuntu/backup-vison.sh
```

---

## Monitoring & Logs

### View Logs

```bash
# All services
docker compose logs -f

# Backend only
docker compose logs -f backend

# Frontend only
docker compose logs -f frontend

# Last 100 lines
docker compose logs --tail 100 backend
```

### Health Checks

```bash
# Backend health
curl https://yourdomain.com/api/health

# Expected response:
# {"status":"healthy","service":"Vison","version":"1.0.0",...}
```

### Uptime Monitoring (Free)

- [UptimeRobot](https://uptimerobot.com) — ping `https://yourdomain.com/api/health` every 5 min
- [Freshping](https://freshping.io) — free monitoring with alerting

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Backend won't start** | Check `docker compose logs backend` — likely missing dependencies or port conflict |
| **"Backend service unavailable"** | Frontend can't reach backend. Verify `BACKEND_URL` env var is correct |
| **File upload fails** | Check Nginx `client_max_body_size` (default 1MB). Set to `100M` |
| **TensorFlow OOM** | Server needs more RAM. Minimum 4 GB for TensorFlow model loading |
| **Crawler not working** | Chrome/Chromium not installed in container. The Dockerfile handles this |
| **FAISS import error** | `faiss-cpu` requires specific CPU features. The app falls back to NumPy |
| **CORS errors** | Update `CORS_ORIGINS` env var to include your frontend domain |
| **Slow first search** | ML model loads on first use. Subsequent searches are fast |
| **Container restarts** | Check `docker compose logs` for crash reason. Common: OOM, port conflicts |
| **SSL certificate issue** | Run `sudo certbot renew` or check Cloudflare SSL settings |

### Quick Diagnostics

```bash
# Check running containers
docker compose ps

# Check resource usage
docker stats

# Check disk space
df -h

# Test backend directly
curl http://localhost:8000/api/health

# Test frontend
curl http://localhost:3000
```

---

<div align="center">
  <b>Need help?</b> Open an issue on the GitHub repository.
</div>
