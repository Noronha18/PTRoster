# --- Estágio 1: Build do Frontend (React + Vite) ---
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# A variável de API em produção geralmente é a mesma URL (relativa)
ENV VITE_API_URL=""
RUN npm run build

# --- Estágio 2: Setup do Backend e Imagem Final ---
FROM python:3.12-slim
WORKDIR /app

# Instala dependências do sistema necessárias para o psycopg2 ou outras libs C
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala o 'uv' para gerenciamento ultra-rápido de dependências
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copia arquivos de dependências do backend e o README (necessário para o pyproject.toml)
COPY backend/pyproject.toml backend/uv.lock README.md ./

# Instala exatamente as versões travadas no uv.lock (sem as de dev).
# Ler só o pyproject.toml pegava versões novas e não testadas: o SQLAlchemy 2.1
# deixou de instalar o greenlet e o alembic quebrava na subida.
RUN uv export --locked --no-dev --no-emit-project --no-hashes -o /tmp/requirements.txt \
    && uv pip install --system -r /tmp/requirements.txt

# Cria um usuário não-privilegiado para rodar o app (Hardening)
RUN useradd -m -u 1000 appuser
USER appuser

# Copia o código do backend com as permissões corretas
COPY --chown=appuser:appuser backend/src ./src
COPY --chown=appuser:appuser backend/alembic ./alembic
COPY --chown=appuser:appuser backend/alembic.ini ./

# Copia o build do frontend para dentro do backend (pasta static)
COPY --from=frontend-build --chown=appuser:appuser /app/frontend/dist ./static

EXPOSE 8080

# Comando para rodar as migrações, criar o admin inicial e iniciar o servidor
CMD ["sh", "-c", "alembic upgrade head && python -m src.create_admin && uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
