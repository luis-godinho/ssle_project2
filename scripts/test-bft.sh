#!/bin/bash

echo "🧪 Testing BFT Consensus Cluster"
echo "================================="
echo ""

API_GATEWAY="http://localhost:8080"

# Test cluster health
echo "1️⃣  Checking cluster health..."
curl -s "${API_GATEWAY}/proxy/order-service/consensus/status" | jq
echo ""

# Create test order
echo "2️⃣  Creating test order (requires 2/3 node agreement)..."
ORDER_DATA='{
  "customer_id": "test-customer",
  "items": [
    {"product_id": "prod-1", "quantity": 2},
    {"product_id": "prod-2", "quantity": 1}
  ]
}'

echo "Sending order: $ORDER_DATA"
curl -s -X POST "${API_GATEWAY}/proxy/order-service/orders" \
  -H "Content-Type: application/json" \
  -d "$ORDER_DATA" | jq
echo ""

echo "✅ BFT test complete!"
echo ""
echo "📝 Check individual node logs:"
echo "  docker logs order-node-1"
echo "  docker logs order-node-2"
echo "  docker logs order-node-3"
echo ""
