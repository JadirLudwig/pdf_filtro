#!/bin/bash
# Script para iniciar o PDF Cleaner e o Túnel Cloudflare
echo "🚀 Iniciando PDF Cleaner..."
docker-compose up -d
echo "✅ Sistema online!"
echo "🔗 Para ver seu link do Cloudflare, use: docker logs pdf-cleaner-tunnel | grep trycloudflare.com"
