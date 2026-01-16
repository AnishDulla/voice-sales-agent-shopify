# Deployment Guide

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Shopify Partner Account
- OpenAI API Access
- LiveKit Cloud or Self-hosted instance

## Environment Setup

### 1. Shopify Configuration

Create a custom app in your Shopify admin:

1. Go to Settings → Apps → Develop apps
2. Create an app with these scopes:
   - `read_products`
   - `read_inventory`
   - `read_orders`
   - `write_cart` (future)

3. Install the app and get credentials:
   - Store URL
   - Access Token

### 2. LiveKit Setup

#### Option A: LiveKit Cloud
1. Sign up at [livekit.io](https://livekit.io)
2. Create a project
3. Get credentials:
   - WebSocket URL
   - API Key
   - API Secret

#### Option B: Self-hosted
```bash
docker run -d \
  -p 7880:7880 \
  -p 7881:7881 \
  -p 7882:7882/udp \
  -v $PWD/livekit.yaml:/livekit.yaml \
  livekit/livekit-server \
  --config /livekit.yaml
```

### 3. Environment Variables

Create `.env` file:

```env
# Shopify
SHOPIFY_STORE_URL=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx
SHOPIFY_API_VERSION=2024-01

# OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxx
OPENAI_MODEL=gpt-4-turbo

# LiveKit
LIVEKIT_URL=wss://your-instance.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxx

# Application
APP_ENV=production
APP_PORT=8000
LOG_LEVEL=info
CORS_ORIGINS=https://your-frontend.com

# Redis (for caching)
REDIS_URL=redis://localhost:6379

# Database (for session storage)
DATABASE_URL=postgresql://user:pass@localhost/voice_agent
```

## Docker Deployment

### 1. Build Image

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/src ./src

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
    env_file:
      - .env
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: voice_agent
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  redis_data:
  postgres_data:
```

### 3. Deploy

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Scale if needed
docker-compose scale backend=3
```

## Cloud Deployment

### AWS Deployment

#### 1. ECS with Fargate

```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URI
docker build -t voice-agent .
docker tag voice-agent:latest $ECR_URI/voice-agent:latest
docker push $ECR_URI/voice-agent:latest

# Deploy with CDK or CloudFormation
cdk deploy VoiceAgentStack
```

#### 2. Lambda + API Gateway (Serverless)

```python
# serverless.yml
service: voice-agent

provider:
  name: aws
  runtime: python3.11
  environment:
    SHOPIFY_STORE_URL: ${env:SHOPIFY_STORE_URL}

functions:
  api:
    handler: src.main.handler
    events:
      - httpApi: '*'
```

### Google Cloud Platform

#### Cloud Run

```bash
# Build and push to Artifact Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/voice-agent

# Deploy
gcloud run deploy voice-agent \
  --image gcr.io/PROJECT_ID/voice-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Heroku

```bash
# Create app
heroku create voice-agent

# Set environment variables
heroku config:set SHOPIFY_STORE_URL=your-store.myshopify.com

# Deploy
git push heroku main

# Scale
heroku ps:scale web=1 worker=1
```

## Production Considerations

### 1. Security

#### API Authentication
```python
# src/infrastructure/api/middleware.py
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_token(credentials = Security(security)):
    token = credentials.credentials
    if not validate_jwt(token):
        raise HTTPException(status_code=401)
```

#### Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

@app.post("/api/voice/session")
@limiter.limit("10/minute")
async def create_session():
    pass
```

### 2. Monitoring

#### Logging
```python
# Structured logging with correlation IDs
import structlog

logger = structlog.get_logger()

logger.info(
    "tool_executed",
    tool_name="search_products",
    session_id=session_id,
    duration_ms=duration
)
```

#### Metrics
```python
# Prometheus metrics
from prometheus_client import Counter, Histogram

tool_executions = Counter(
    'tool_executions_total',
    'Total tool executions',
    ['tool_name', 'status']
)

response_time = Histogram(
    'response_time_seconds',
    'Response time in seconds'
)
```

### 3. Scaling

#### Horizontal Scaling
- Use container orchestration (K8s, ECS)
- Load balance WebSocket connections
- Share session state via Redis

#### Caching Strategy
```python
# Redis caching for products
import redis
import json

cache = redis.Redis.from_url(REDIS_URL)

async def get_products(category: str):
    # Check cache
    cached = cache.get(f"products:{category}")
    if cached:
        return json.loads(cached)
    
    # Fetch from Shopify
    products = await shopify.get_products(category)
    
    # Cache for 5 minutes
    cache.setex(
        f"products:{category}",
        300,
        json.dumps(products)
    )
    return products
```

### 4. High Availability

#### Health Checks
```python
@app.get("/health")
async def health_check():
    checks = {
        "api": "healthy",
        "shopify": await check_shopify_connection(),
        "livekit": await check_livekit_connection(),
        "redis": await check_redis_connection()
    }
    
    if all(v == "healthy" for v in checks.values()):
        return {"status": "healthy", "checks": checks}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "checks": checks}
        )
```

#### Graceful Shutdown
```python
import signal
import asyncio

async def shutdown(signal, loop):
    logger.info(f"Received exit signal {signal.name}")
    
    # Close WebSocket connections
    await close_all_connections()
    
    # Complete pending tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    loop.stop()

# Register handlers
for sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(sig, lambda s, f: asyncio.create_task(shutdown(s, loop)))
```

## Deployment Checklist

- [ ] Environment variables configured
- [ ] SSL/TLS certificates installed
- [ ] Database migrations run
- [ ] Redis cache configured
- [ ] LiveKit room settings configured
- [ ] Monitoring and alerting setup
- [ ] Backup strategy implemented
- [ ] Rate limiting configured
- [ ] Health checks passing
- [ ] Load testing completed
- [ ] Rollback plan documented

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failures**
   - Check firewall rules for ports 7880-7882
   - Verify LiveKit URL and credentials
   - Ensure SSL certificates are valid

2. **High Latency**
   - Check Redis cache hit rates
   - Monitor Shopify API rate limits
   - Review OpenAI API response times

3. **Memory Issues**
   - Implement connection pooling
   - Clear expired sessions
   - Monitor memory usage patterns

### Debug Mode

Enable detailed logging:
```python
# .env
LOG_LEVEL=debug
DEBUG_TOOLS=true
TRACE_REQUESTS=true
```

### Support

For deployment issues:
- Check logs: `docker-compose logs -f backend`
- Review metrics dashboard
- Contact support with correlation ID