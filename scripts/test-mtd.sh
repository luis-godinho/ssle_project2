#!/usr/bin/env bash
set -e

echo "🎯 Testing Moving Target Defense (MTD)..."
echo "============================================"
echo ""

# Test 1: Check service registry
echo "Test 1: Checking service registry..."
services=$(curl -s http://localhost:5000/services || echo "ERROR")

if [[ "$services" == "ERROR" ]]; then
    echo "❌ Service registry not reachable. Is docker-compose running?"
    exit 1
fi

echo "✅ Registered services:"
echo "$services" | jq '.services[] | {name, port, healthy, rotation_count}'
echo ""

# Get initial port
initial_port=$(echo "$services" | jq -r '.services[] | select(.name == "product-service") | .port')
echo "📌 Product service initial port: $initial_port"
echo ""

# Test 2: Verify service is accessible
echo "Test 2: Verifying product service is accessible..."
products=$(curl -s http://localhost:8080/proxy/product-service/api/products || echo "ERROR")

if [[ "$products" != "ERROR" ]]; then
    echo "✅ Product service accessible!"
    echo "$products" | jq '{products: (.products | length), service_port}'
else
    echo "❌ Product service not responding"
    exit 1
fi
echo ""

# Test 3: Port scan before rotation
echo "Test 3: Active ports BEFORE rotation (8001-8011):"
active_ports_before=()
for port in {8001..8011}; do
    if nc -z -w1 localhost $port 2>/dev/null; then
        echo "  ✅ Port $port: OPEN"
        active_ports_before+=($port)
    fi
done
echo ""

# Test 4: Trigger MTD rotation
echo "Test 4: Triggering MTD rotation..."
rotation=$(curl -s -X POST http://localhost:5000/rotate/product-service || echo "ERROR")

if [[ "$rotation" == "ERROR" ]]; then
    echo "❌ Failed to trigger rotation"
    exit 1
fi

echo "✅ Rotation command sent:"
echo "$rotation" | jq '{service, old_port, new_port, rotation_count}'

new_port=$(echo "$rotation" | jq -r '.new_port')
old_port=$(echo "$rotation" | jq -r '.old_port')

echo ""
echo "⏳ Waiting for service to rotate from port $old_port to $new_port..."
echo "   (This takes ~5 seconds for graceful transition)"

for i in {1..10}; do
    echo -n "."
    sleep 1

    # Check if new port is listening
    if nc -z -w1 localhost $new_port 2>/dev/null; then
        echo ""
        echo "✅ New port $new_port is now OPEN!"
        break
    fi
done
echo ""

# Test 5: Verify service still works on new port
echo "Test 5: Verifying service on NEW port ($new_port)..."
sleep 2

# Direct connection to new port
products_new=$(curl -s http://localhost:$new_port/api/products || echo "ERROR")

if [[ "$products_new" != "ERROR" ]]; then
    echo "✅ Service responding on new port $new_port!"
    echo "$products_new" | jq '{products: (.products | length), service_port: .external_port}'
else
    echo "⚠️  Service not yet responding on new port (may need more time)"
fi
echo ""

# Test 6: Verify via API gateway (uses registry discovery)
echo "Test 6: Verifying via API gateway (should auto-discover new port)..."
sleep 2

products_gateway=$(curl -s http://localhost:8080/proxy/product-service/api/products || echo "ERROR")

if [[ "$products_gateway" != "ERROR" ]]; then
    gateway_port=$(echo "$products_gateway" | jq -r '.external_port')
    echo "✅ API Gateway successfully routed to port: $gateway_port"

    if [[ "$gateway_port" == "$new_port" ]]; then
        echo "✅ 🎉 MTD ROTATION SUCCESSFUL! Gateway now using new port!"
    else
        echo "⚠️  Gateway still using old port (may need registry sync)"
    fi
else
    echo "❌ Gateway not responding"
fi
echo ""

# Test 7: Port scan after rotation
echo "Test 7: Active ports AFTER rotation (8001-8011):"
active_ports_after=()
for port in {8001..8011}; do
    if nc -z -w1 localhost $port 2>/dev/null; then
        if [[ " ${active_ports_before[@]} " =~ " ${port} " ]]; then
            echo "  🔵 Port $port: OPEN (unchanged)"
        else
            echo "  ✅ Port $port: OPEN (NEW!)"
        fi
        active_ports_after+=($port)
    fi
done

# Show closed ports
for port in "${active_ports_before[@]}"; do
    if ! [[ " ${active_ports_after[@]} " =~ " ${port} " ]]; then
        echo "  🛑 Port $port: CLOSED (rotated away)"
    fi
done
echo ""

# Test 8: Check registry status
echo "Test 8: Final registry status:"
final_status=$(curl -s http://localhost:5000/services/status)
echo "$final_status" | jq '.services[] | select(.name == "product-service") | {name, port, rotation_count, healthy, seconds_since_heartbeat}'
echo ""

echo "🎉 MTD Testing Complete!"
echo "============================================"
echo ""
echo "💡 Summary:"
echo "  - Initial port: $initial_port"
echo "  - New port: $new_port"
echo "  - Rotation successful: $([ "$new_port" != "$initial_port" ] && echo "✅ YES" || echo "❌ NO")"
echo ""
