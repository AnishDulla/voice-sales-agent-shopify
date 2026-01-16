#!/bin/bash

# Deployment script

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Deploying Voice Sales Agent..."

# Parse arguments
ENVIRONMENT="staging"
SKIP_TESTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "📦 Deployment target: $ENVIRONMENT"

# Run tests unless skipped
if [ "$SKIP_TESTS" = false ]; then
    echo "🧪 Running tests..."
    "$SCRIPT_DIR/test.sh"
fi

# Build Docker image
echo "🐳 Building Docker image..."
cd "$PROJECT_ROOT"
docker build -t voice-sales-agent:latest -f Dockerfile .

# Tag for registry
if [ "$ENVIRONMENT" = "production" ]; then
    REGISTRY_URL="${DOCKER_REGISTRY:-your-registry.com}"
    IMAGE_TAG="$REGISTRY_URL/voice-sales-agent:$(git rev-parse --short HEAD)"
    
    echo "🏷️  Tagging image: $IMAGE_TAG"
    docker tag voice-sales-agent:latest "$IMAGE_TAG"
    
    echo "⬆️  Pushing to registry..."
    docker push "$IMAGE_TAG"
    
    echo "🎯 Deploying to production..."
    # Add your deployment commands here
    # kubectl apply -f k8s/
    # or
    # docker-compose -f docker-compose.prod.yml up -d
    # or
    # aws ecs update-service --cluster prod --service voice-agent --force-new-deployment
    
elif [ "$ENVIRONMENT" = "staging" ]; then
    echo "🎯 Deploying to staging..."
    docker-compose -f docker-compose.yml up -d
fi

echo "✅ Deployment complete!"
echo "🔍 Check application at: http://localhost:8000/health"