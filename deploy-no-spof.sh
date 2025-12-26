#!/bin/bash
set -e

echo "🚀 Deploying BFT Cluster with No Single Point of Failure"
echo "========================================================="
echo ""

echo "📦 Step 1: Stopping existing containers..."
docker-compose down

echo "🔨 Step 2: Rebuilding services..."
docker-compose build --no-cache order-node-1 order-node-2 order-node-3 registry

echo "🚀 Step 3: Starting all services..."
docker-compose up -d

echo "⏳ Step 4: Waiting for services to initialize (60s)..."
sleep 60

echo "✅ Step 5: Verifying registrations..."
echo "Expected: All 3 nodes + load-balanced entry = 4 registrations"
curl -s http://localhost:5000/services | jq '.services[] | select(.name | startswith("order-service")) | {name, host, port, healthy, metadata}'

echo ""
echo "✅ Step 6: Testing cluster health..."
curl -s http://localhost:8102/consensus/status | jq '{healthy_nodes, quorum_available, quorum_size, vault_auth_enabled}'

echo ""
echo "✅ Step 7: Testing load balancing (3 requests)..."
for i in {1..3}; do
  echo "Request $i:"
  curl -s http://localhost:8080/proxy/order-service/health | jq '{node, role}'
  sleep 1
done

echo ""
echo "🎉 Deployment Complete!"
echo "========================================================="
echo "📖 See TESTING_NO_SPOF.md for comprehensive tests"
echo ""
echo "Quick tests:"
echo "  - Load balancing: for i in {1..6}; do curl -s http://localhost:8080/proxy/order-service/health | jq .node; done"
echo "  - Stop node-1:    docker stop order-node-1 && test-bft"
echo "  - Full test:      ./test-no-spof.sh"
echo ""
