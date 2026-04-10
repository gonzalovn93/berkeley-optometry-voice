#!/bin/bash
set -e

SERVER="ubuntu@52.34.105.180"
KEY="~/key_session_gonza.pem"
REMOTE_DIR="/home/ubuntu/berkeley-optometry-voice"

echo "==> Deploying Berkeley Optometry Voice Agent..."

# 1. Clone or pull latest code
ssh -i $KEY $SERVER "
    if [ -d $REMOTE_DIR ]; then
        cd $REMOTE_DIR && git pull origin main
    else
        git clone https://github.com/gonzalovn93/berkeley-optometry-voice.git $REMOTE_DIR
    fi
"

# 2. Install dependencies
ssh -i $KEY $SERVER "
    cd $REMOTE_DIR
    pip3 install -r requirements.txt --quiet
"

# 3. Copy .env with API keys
scp -i $KEY ~/.berkeley-optometry-env $SERVER:$REMOTE_DIR/.env 2>/dev/null || echo "   (skipping .env — set keys manually if first deploy)"

# 4. Install systemd service
ssh -i $KEY $SERVER "
    sudo cp $REMOTE_DIR/deployment/berkeley-optometry.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable berkeley-optometry
    sudo systemctl restart berkeley-optometry
"

# 5. Install nginx config
ssh -i $KEY $SERVER "
    sudo cp $REMOTE_DIR/deployment/nginx-optometry.conf /etc/nginx/sites-available/optometry
    sudo ln -sf /etc/nginx/sites-available/optometry /etc/nginx/sites-enabled/optometry
    sudo nginx -t && sudo systemctl reload nginx
"

echo "==> Checking service status..."
ssh -i $KEY $SERVER "sudo systemctl status berkeley-optometry --no-pager -l"

echo ""
echo "==> Deploy complete! Service running on port 8001"
echo "    Access via: http://52.34.105.180:8001 (direct)"
echo "    Or via nginx: http://optometry.letsgoplai.com (if DNS configured)"
