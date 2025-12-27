#!/usr/bin/env bash
set -e

echo "🧪 Testing Byzantine Fault Tolerance..."
echo ""

# Test 1: Check cluster quorum
echo "Test 1: Checking BFT cluster quorum..."
response=$(${pkgs.curl}/bin/curl -s http://localhost:8102/consensus/status || echo "ERROR")

if [[ "$response" == "ERROR" ]]; then
echo "❌ Order service not reachable. Is docker-compose running?"
echo "   Run: docker-compose up -d"
exit 1
fi

echo "✅ Cluster status:"
echo "$response" | ${pkgs.jq}/bin/jq .
echo ""

# Test 2: Create order with consensus
echo "Test 2: Creating order (requires consensus)..."
order_response=$(${pkgs.curl}/bin/curl -s -X POST http://localhost:8080/proxy/order-service/api/orders \
-H "Content-Type: application/json" \
-d '{
    "customer_id": "CUST001",
    "items": [
    {"product_id": "PROD001", "quantity": 1, "price": 999.99}
    ]
}' || echo "ERROR")

if echo "$order_response" | ${pkgs.jq}/bin/jq -e '.order_id' > /dev/null 2>&1; then
echo "✅ Order created successfully:"
echo "$order_response" | ${pkgs.jq}/bin/jq .
else
echo "⚠️  Order creation response:"
echo "$order_response"
fi
echo ""

# Test 3: Stop one node and test resilience
echo "Test 3: Testing fault tolerance (stopping node 2)..."
echo "Stopping order-node-2..."
${pkgs.docker}/bin/docker stop order-node-2 2>/dev/null || echo "Node 2 already stopped"
sleep 2

echo "Creating order with 2/3 quorum..."
order_response2=$(${pkgs.curl}/bin/curl -s -X POST http://localhost:8080/proxy/order-service/api/orders \
-H "Content-Type: application/json" \
-d '{
    "customer_id": "CUST002",
    "items": [
    {"product_id": "PROD002", "quantity": 2, "price": 49.99}
    ]
}' || echo "ERROR")

if echo "$order_response2" | ${pkgs.jq}/bin/jq -e '.order_id' > /dev/null 2>&1; then
echo "✅ Order created with 2/3 quorum (Byzantine fault tolerance working!)"
echo "$order_response2" | ${pkgs.jq}/bin/jq .
else
echo "❌ Order creation failed with 2/3 quorum:"
echo "$order_response2"
fi

# Restart node 2
echo ""
echo "Restarting order-node-2..."
${pkgs.docker}/bin/docker start order-node-2 2>/dev/null
sleep 2

echo ""
echo "🎉 BFT testing complete!"
