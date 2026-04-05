#!/bin/bash
# Script para iniciar o PDF Cleaner e o Túnel Cloudflare
echo "🚀 Iniciando PDF Cleaner..."
docker-compose up -d

echo "⏳ Aguardando o túnel Cloudflare estabelecer conexão..."
sleep 8

echo "✅ Sistema online!"
echo "🔗 Seu link de acesso externo é:"
docker logs pdf-cleaner-tunnel 2>&1 | grep -o 'https://.*\.trycloudflare\.com' | head -n 1
