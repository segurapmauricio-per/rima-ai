# RIMA AI — Deploy Script
# Ejecutar desde: C:\Users\Mauricio\projects\rima-ai\
# Requiere: Git Bash o PowerShell con OpenSSH instalado

$VPS_IP = "2.24.73.213"
$VPS_USER = "root"
$VPS_PASS = "LZ;Qix'VIb8aZ1.2Nt,3"
$REPO = "https://github.com/segurapmauricio-per/rima-ai.git"
$APP_DIR = "/root/rima-ai"
$DOMAIN = "rima.n8n-ghl.com"
$LOCAL_ENV = "$PSScriptRoot\..\\.env"

Write-Host "=== RIMA AI Deploy ===" -ForegroundColor Cyan
Write-Host "VPS: $VPS_USER@$VPS_IP"
Write-Host "App: $APP_DIR"
Write-Host "Domain: $DOMAIN"
Write-Host ""

# Verificar que existe el .env local
if (-not (Test-Path $LOCAL_ENV)) {
    Write-Host "ERROR: No se encuentra .env en $LOCAL_ENV" -ForegroundColor Red
    exit 1
}

Write-Host "[1/7] Copiando .env al servidor..." -ForegroundColor Yellow
$envContent = Get-Content $LOCAL_ENV -Raw
$sshCmd = "echo '$envContent' > $APP_DIR/.env"

# Usamos plink si está disponible, sino ssh
$sshBin = "ssh"
$scpBin = "scp"

# Copiar .env via scp
& $scpBin -o StrictHostKeyChecking=no `
    $LOCAL_ENV `
    "${VPS_USER}@${VPS_IP}:${APP_DIR}/.env.tmp" 2>&1

Write-Host "[2/7] Instalando dependencias del sistema..." -ForegroundColor Yellow
$setup = @"
set -e

# Actualizar e instalar paquetes base
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx curl

echo '[OK] Sistema actualizado'
"@

& $sshBin -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_IP}" $setup

Write-Host "[3/7] Clonando/actualizando repo..." -ForegroundColor Yellow
$deploy = @"
set -e

if [ -d "$APP_DIR" ]; then
    echo 'Actualizando repo existente...'
    cd $APP_DIR
    git fetch origin
    git reset --hard origin/main
else
    echo 'Clonando repo...'
    git clone $REPO $APP_DIR
    cd $APP_DIR
fi

echo '[OK] Repo actualizado'
"@

& $sshBin -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_IP}" $deploy

Write-Host "[4/7] Configurando entorno Python..." -ForegroundColor Yellow
$python = @"
set -e
cd $APP_DIR

# Crear venv si no existe
if [ ! -d venv ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo '[OK] Dependencias Python instaladas'
"@

& $sshBin -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_IP}" $python

Write-Host "[5/7] Moviendo .env..." -ForegroundColor Yellow
& $sshBin -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_IP}" "mv $APP_DIR/.env.tmp $APP_DIR/.env && chmod 600 $APP_DIR/.env && echo '[OK] .env configurado'"

Write-Host "[6/7] Configurando systemd service..." -ForegroundColor Yellow
$systemd = @"
cat > /etc/systemd/system/rima.service << 'EOF'
[Unit]
Description=RIMA AI FastAPI
After=network.target

[Service]
User=root
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable rima
systemctl restart rima
sleep 3
systemctl status rima --no-pager | head -20
echo '[OK] Servicio rima activo'
"@

& $sshBin -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_IP}" $systemd

Write-Host "[7/7] Configurando nginx + SSL..." -ForegroundColor Yellow
$nginx = @"
cat > /etc/nginx/sites-available/rima << 'EOF'
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }

    location /uploads/ {
        alias $APP_DIR/uploads/;
        expires 7d;
    }
}
EOF

ln -sf /etc/nginx/sites-available/rima /etc/nginx/sites-enabled/rima
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# SSL con certbot
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@rima.ai --redirect 2>&1 || echo 'SSL: verificar DNS primero'

echo '[OK] Nginx configurado'
"@

& $sshBin -o StrictHostKeyChecking=no "${VPS_USER}@${VPS_IP}" $nginx

Write-Host ""
Write-Host "=== Deploy completado ===" -ForegroundColor Green
Write-Host "URL: https://$DOMAIN" -ForegroundColor Cyan
Write-Host "Logs: ssh root@$VPS_IP 'journalctl -u rima -f'"
