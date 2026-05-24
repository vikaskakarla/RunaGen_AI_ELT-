# RunaGen AI — Complete AWS EC2 Setup & Deployment Guide

This guide provides step-by-step instructions to set up an **AWS EC2** instance and configure **GitHub Actions** for the automated deployment of the **RunaGen AI** stack (FastAPI Backend, Live Pipeline Scheduler, and Frontend Dashboard).

---

## 🏗️ Architecture Overview

When deployed, the application will run in a containerized environment managed by **Docker Compose**:
1. **`runagen-nginx` (Port 80)**: Serves static frontend files and acts as a reverse proxy, forwarding API requests to the backend.
2. **`runagen-api` (Port 8080 - Internal)**: Runs the FastAPI app with Uvicorn.
3. **`runagen-scheduler` (Background)**: Runs `run_live_pipeline.py` in production mode to perform hourly ingestion, 4-hour ETL runs, and daily ML model retraining.
4. **`model_data` (Shared Docker Volume)**: Persists trained Scikit-Learn/XGBoost models, making them instantly available to the FastAPI API without container restarts.

---

## 📋 Step 1: Launch your AWS EC2 Instance

1. Log in to your **AWS Management Console**.
2. Navigate to **EC2** and click **Launch instance**.
3. **Name**: `runagen-prod-server`
4. **Application and OS Image (AMI)**: Select **Ubuntu Server 24.04 LTS** (or **Ubuntu Server 22.04 LTS**), 64-bit (x86) architecture.
5. **Instance Type**: Select **`m7i-flex.large`** (2 vCPUs, 8 GB RAM). 
   > [!NOTE]
   > This instance type provides plenty of memory (8 GB) to avoid Out-Of-Memory (OOM) crashes during ML training while fitting perfectly within your operational budget.
6. **Key Pair (login)**: Click **Create new key pair**.
   - Key pair name: `runagen-key`
   - Key pair type: `RSA`
   - Private key file format: `.pem`
   - Click **Create key pair** and save the downloaded `runagen-key.pem` file securely on your computer.
7. **Network Settings**:
   - Check **Allow SSH traffic from** -> Select **Anywhere** (or **My IP** for maximum security).
   - Check **Allow HTTP traffic from the internet** (Port 80).
   - Check **Allow HTTPS traffic from the internet** (Port 443).
8. **Configure Storage**: Set size to **20 GiB** (using `gp3` storage) to accommodate Docker image caching and localized log outputs.
9. Click **Launch instance**. Go back to the EC2 instances list and copy your instance's **Public IPv4 Address** (e.g., `54.210.34.12`).

---

## 🔑 Step 2: Set Key Permissions & Verify SSH

Before using the `.pem` file, secure its permissions so SSH clients do not reject it:

### On Windows (PowerShell)
Open PowerShell in the folder where your `.pem` key is saved and run:
```powershell
# Disable inheritance and grant exclusive read access to your Windows user
icacls.exe .\runagen-key.pem /inheritance:r /grant:r "$($env:username):R"
```

### On macOS / Linux (Terminal)
```bash
chmod 400 runagen-key.pem
```

Test your connection to the server:
```bash
ssh -i runagen-key.pem ubuntu@<YOUR_EC2_PUBLIC_IP>
```
Type `yes` if prompted to verify host authenticity. Once you log in, type `exit` to return to your local machine.

---

## 🐳 Step 3: Install Docker & Docker Compose on EC2

Log back into your EC2 instance (`ssh -i runagen-key.pem ubuntu@<YOUR_EC2_PUBLIC_IP>`) and run:

```bash
# Update local packages
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker and Docker Compose v2
sudo apt-get install -y docker.io docker-compose-v2

# Start and enable Docker service on system boot
sudo systemctl enable docker
sudo systemctl start docker

# Add ubuntu user to the docker group so you don't need 'sudo' for docker commands
sudo usermod -aG docker ubuntu

# LOG OUT of the session to apply group settings
exit
```

Reconnect to the instance:
```bash
ssh -i runagen-key.pem ubuntu@<YOUR_EC2_PUBLIC_IP>
```
Verify Docker works without sudo:
```bash
docker ps
```
*(It should print an empty table header without permission errors)*

---

## 🔒 Step 4: Configure Production Environment (`.env`)

To keep database and Google Cloud keys secure, we load them from a local `.env` file on the EC2 instance instead of committing them to Git.

1. On the EC2 instance, create the application deployment directory:
   ```bash
   mkdir -p ~/runagen-app
   cd ~/runagen-app
   ```
2. Create the `.env` file:
   ```bash
   nano .env
   ```
3. Copy the template below, replace the values with your actual credentials, paste it into nano, and save (`Ctrl+O`, `Enter`, `Ctrl+X`):

```ini
# Environment Type
ENVIRONMENT=cloud

# MongoDB Settings
MONGO_URI=mongodb+srv://nasasujith265_db_user:z9d9cSbDedbyA1aA@cluster0runagen.dbw0rxl.mongodb.net/runagen_ml_warehouse?retryWrites=true&w=majority&appName=Cluster0runagen
MONGO_DB=runagen_ml_warehouse

# Adzuna API Credentials
ADZUNA_APP_ID=42cf8c86
ADZUNA_APP_KEY=1706dc3ca402aab909d9b8ba7f57092a

# Google Cloud Platform (BigQuery) Settings
GCP_PROJECT_ID=runagen-ai
# Paste the content of credentials/bigquery-key.json as a SINGLE LINE JSON string here:
GCP_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"runagen-ai","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}
```

> [!IMPORTANT]
> **Formatting GCP_SERVICE_ACCOUNT_JSON**:
> The `credentials/` folder is ignored by Docker during builds (`.dockerignore`). To authenticate with BigQuery, you must supply the service account JSON contents via the `GCP_SERVICE_ACCOUNT_JSON` environment variable.
>
> To convert your `bigquery-key.json` file into a clean, single-line JSON string suitable for `.env`:
> - **On Windows (PowerShell)**:
>   ```powershell
>   (Get-Content .\credentials\bigquery-key.json -Raw) -replace '\s+', '' | Set-Clipboard
>   ```
>   *(Then paste directly into the `.env` file on your server)*
> - **On macOS/Linux**:
>   ```bash
>   tr -d '\n' < credentials/bigquery-key.json | tr -d ' ' | pbcopy
>   ```

---

## 🛠️ Step 5: Configure GitHub Secrets

Deployments are automated. Every time you push to the `main` branch, GitHub Actions will compile the Docker image, transfer configurations, and reload the server.

Go to your repository on GitHub:
1. Click **Settings** (top tabs).
2. On the left sidebar, click **Secrets and variables** -> **Actions**.
3. Under the **Repository secrets** section, click **New repository secret** and add the following three secrets:

| Secret Name | Value | Description |
| :--- | :--- | :--- |
| **`EC2_HOST`** | `YOUR_EC2_PUBLIC_IP` | The public IP address of your EC2 instance (e.g. `54.210.34.12`). |
| **`EC2_USERNAME`** | `ubuntu` | The default admin user for Ubuntu AMIs. |
| **`EC2_SSH_KEY`** | *[Content of `.pem` key]* | Open `runagen-key.pem` in a text editor, copy **everything** (including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`), and paste it. |

---

## 🚀 Step 6: Trigger the Deployment

Simply push a change (e.g., a dummy commit, or your deployment configurations) to the `main` branch:

```bash
git add .
git commit -m "chore: setup docker-compose deploy to EC2"
git push origin main
```

Navigate to the **Actions** tab in your GitHub repository to track progress. The build will:
1. Check out your codebase.
2. Build the production Docker image.
3. Compress the image into a tarball.
4. Securely copy the configurations (`docker-compose.yml`, `nginx.conf`), static frontend folder (`web/`), and the tarball to your EC2 instance.
5. Extract and load the Docker image on the server.
6. Launch all containers in detached daemon mode.

---

## 🔍 Step 7: Verify & Manage your Deployment

Once the GitHub Actions workflow finishes successfully, log back into your EC2 instance to verify and monitor your stack.

### 1. Check Container Health
```bash
docker ps
```
You should see all three containers running:
- `runagen-nginx` (Listening on Port 80, proxying requests)
- `runagen-api` (FastAPI backend)
- `runagen-scheduler` (Dedicated continuous Python pipeline worker)

### 2. Monitor Live Logs
- **FastAPI API Logs**:
  ```bash
  docker logs -f runagen-api
  ```
- **Live Pipeline Scheduler Logs**:
  ```bash
  docker logs -f runagen-scheduler
  ```
- **Nginx Proxy Logs**:
  ```bash
  docker logs -f runagen-nginx
  ```

### 3. Check App in Browser
- Open your browser and navigate to `http://<YOUR_EC2_PUBLIC_IP>/`. You should see the fully operational RunaGen dashboard.
- Navigate to `http://<YOUR_EC2_PUBLIC_IP>/health` to see the FastAPI system health check status.

### 4. Restarting the Stack Manually
If you ever change your `.env` file on EC2, reload the containers to apply changes:
```bash
cd ~/runagen-app
docker compose down
docker compose up -d
```
