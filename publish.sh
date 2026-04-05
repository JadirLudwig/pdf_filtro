#!/bin/bash
# Script de Publicação Automática: PDF Cleaner

echo "=== Publicando no GitHub ==="
# git init          # Descomente caso ainda não seja um repositório git
# git remote add origin URL_DO_SEU_REPO_AQUI
git add .
git commit -m "update: Atualização de formato TXT"
# git push -u origin main

echo "=== Publicando no DockerHub (ludwig91/pdf_filtro) ==="
# docker login  # Descomente e faça login caso ainda não tenha autenticado seu CLI
docker build -t ludwig91/pdf_filtro:latest .
docker push ludwig91/pdf_filtro:latest

echo "✅ Deploy Concluído!"
