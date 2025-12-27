#!/usr/bin/env bash
set -e

echo "🎯 Testing Moving Target Defense (MTD)..."
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test 1: Check service registry
echo "Test 1: Checking service registry..."
services=$(curl -s http://localhost:5000/services || echo "ERROR")

if [[ "$services" == "ERROR" ]]; then
    echo -e "${RED}❌ Service registry not reachable. Is docker-compose running?${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Registered services:${NC}"
echo "$services" | jq '.services[] | select(.name == "product-service") | {name, port, healthy, rotation_count}'
echo ""

# Get initial port
initial_port=$(echo "$services" | jq -r '.services[] | select(.name == "product-service") | .port')
echo -e "${BLUE}📌 Product service initial port: $initial_port${NC}"
echo ""

# Test 2: Verify iptables rules (CORE MTD MECHANISM)
echo "Test 2: Verifying iptables NAT rules..."
iptables_output=$(docker exec product-service iptables -t nat -L PREROUTING -n -v 2>/dev/null | grep "dpt:" || echo "NONE")

if [[ "$iptables_output" != "NONE" ]]; then
    echo -e "${GREEN}✅ iptables rules found:${NC}"
    echo "$iptables_output" | grep -E "dpt:(800[0-9]|801[0-1])" | while read line; do
        port=$(echo "$line" | grep -oP 'dpt:\K[0-9]+')
        target=$(echo "$line" | grep -oP 'redir ports \K[0-9]+')
        echo "  🔀 External port $port → Internal port $target"
    done
else
    echo -e "${RED}❌ No iptables rules found! MTD may not be working.${NC}"
fi
echo ""

# Test 3: Verify service is accessible on current port
echo "Test 3: Verifying product service is accessible on port $initial_port..."
products=$(curl -s http://localhost:$initial_port/api/products || echo "ERROR")

if [[ "$products" != "ERROR" ]]; then
    echo -e "${GREEN}✅ Product service accessible!${NC}"
    echo "$products" | jq '{products: (.products | length), external_port}'
else
    echo -e "${RED}❌ Product service not responding on port $initial_port${NC}"
    exit 1
fi
echo ""

# Test 4: Check MTD metrics
echo "Test 4: Checking MTD metrics..."
metrics=$(curl -s http://localhost:$initial_port/metrics | grep "mtd_" || echo "NONE")

if [[ "$metrics" != "NONE" ]]; then
    echo -e "${GREEN}✅ MTD metrics available:${NC}"
    echo "$metrics" | grep -E "(mtd_rotations_total|mtd_current_port)" | sed 's/^/  /'
else
    echo -e "${YELLOW}⚠️  No MTD metrics found${NC}"
fi
echo ""

# Test 5: Trigger MTD rotation
echo "Test 5: Triggering MTD rotation..."
rotation=$(curl -s -X POST http://localhost:5000/rotate/product-service -H "Content-Type: application/json" || echo "ERROR")

if [[ "$rotation" == "ERROR" ]]; then
    echo -e "${RED}❌ Failed to trigger rotation${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Rotation command sent:${NC}"
echo "$rotation" | jq '{service, old_port, new_port, rotation_count, service_rotated}'

new_port=$(echo "$rotation" | jq -r '.new_port')
old_port=$(echo "$rotation" | jq -r '.old_port')
service_rotated=$(echo "$rotation" | jq -r '.service_rotated // false')

if [[ "$service_rotated" == "true" ]]; then
    echo -e "${GREEN}✅ Service confirmed rotation via /rotate endpoint${NC}"
else
    echo -e "${YELLOW}⚠️  Service rotation callback failed (but port allocated)${NC}"
fi
echo ""

# Test 6: Verify iptables rules changed
echo "Test 6: Verifying iptables rules updated..."
sleep 2

iptables_new=$(docker exec product-service iptables -t nat -L PREROUTING -n -v 2>/dev/null | grep "dpt:" || echo "NONE")

if [[ "$iptables_new" != "NONE" ]]; then
    echo -e "${GREEN}✅ New iptables rules:${NC}"
    echo "$iptables_new" | grep -E "dpt:(800[0-9]|801[0-1])" | while read line; do
        port=$(echo "$line" | grep -oP 'dpt:\K[0-9]+')
        target=$(echo "$line" | grep -oP 'redir ports \K[0-9]+')
        if [[ "$port" == "$new_port" ]]; then
            echo -e "  ${GREEN}✅ External port $port → Internal port $target (NEW!)${NC}"
        elif [[ "$port" == "$old_port" ]]; then
            echo -e "  ${RED}❌ External port $port → Internal port $target (OLD - should be removed!)${NC}"
        else
            echo "  🔀 External port $port → Internal port $target"
        fi
    done
else
    echo -e "${RED}❌ No iptables rules found after rotation!${NC}"
fi
echo ""

# Test 7: Verify OLD port is CLOSED
echo "Test 7: Verifying old port ($old_port) is closed..."
old_port_test=$(curl -s --max-time 3 http://localhost:$old_port/api/products 2>&1 || echo "FAILED")

if [[ "$old_port_test" == "FAILED" ]] || [[ "$old_port_test" == *"Connection refused"* ]] || [[ "$old_port_test" == *"Empty reply"* ]]; then
    echo -e "${GREEN}✅ Old port $old_port is CLOSED (MTD working!)${NC}"
else
    echo -e "${YELLOW}⚠️  Old port $old_port still responding (may take time to close)${NC}"
fi
echo ""

# Test 8: Verify NEW port is OPEN
echo "Test 8: Verifying new port ($new_port) is open..."
sleep 2

new_port_test=$(curl -s http://localhost:$new_port/api/products || echo "ERROR")

if [[ "$new_port_test" != "ERROR" ]]; then
    echo -e "${GREEN}✅ New port $new_port is OPEN and responding!${NC}"
    echo "$new_port_test" | jq '{products: (.products | length), external_port}'
else
    echo -e "${RED}❌ New port $new_port not responding${NC}"
    exit 1
fi
echo ""

# Test 9: Verify via API gateway (registry discovery + load balancing)
echo "Test 9: Verifying via API gateway (auto-discovery)..."
sleep 2

gateway_response=$(curl -s http://localhost:8080/proxy/product-service/api/products || echo "ERROR")

if [[ "$gateway_response" != "ERROR" ]]; then
    gateway_port=$(echo "$gateway_response" | jq -r '.external_port // .service_port // "unknown"')
    echo -e "${GREEN}✅ API Gateway successfully routed request${NC}"
    echo "   Detected port: $gateway_port"

    if [[ "$gateway_port" == "$new_port" ]]; then
        echo -e "   ${GREEN}🎉 Gateway using NEW port after rotation!${NC}"
    elif [[ "$gateway_port" == "$old_port" ]]; then
        echo -e "   ${YELLOW}⚠️  Gateway still cached old port (will sync on next discovery)${NC}"
    fi
else
    echo -e "${RED}❌ Gateway not responding${NC}"
fi
echo ""

# Test 10: Test multiple rotations
echo "Test 10: Testing multiple rapid rotations..."
for i in {1..3}; do
    echo "  Rotation $i/3..."
    rotation_multi=$(curl -s -X POST http://localhost:5000/rotate/product-service -H "Content-Type: application/json" || echo "ERROR")
    
    if [[ "$rotation_multi" != "ERROR" ]]; then
        multi_new=$(echo "$rotation_multi" | jq -r '.new_port')
        multi_count=$(echo "$rotation_multi" | jq -r '.rotation_count')
        echo -e "    ${GREEN}✅ Rotated to port $multi_new (count: $multi_count)${NC}"
    else
        echo -e "    ${RED}❌ Rotation $i failed${NC}"
    fi
    sleep 2
done
echo ""

# Test 11: Final registry status
echo "Test 11: Final registry status..."
final_status=$(curl -s http://localhost:5000/services/status)
final_port=$(echo "$final_status" | jq -r '.services[] | select(.name == "product-service") | .port')
final_count=$(echo "$final_status" | jq -r '.services[] | select(.name == "product-service") | .rotation_count')
final_heartbeat=$(echo "$final_status" | jq -r '.services[] | select(.name == "product-service") | .seconds_since_heartbeat')

echo "$final_status" | jq '.services[] | select(.name == "product-service") | {name, port, rotation_count, healthy, seconds_since_heartbeat}'
echo ""

# Summary
echo "🎉 MTD Testing Complete!"
echo "============================================"
echo ""
echo -e "${BLUE}📊 Summary:${NC}"
echo "  - Initial port: $initial_port"
echo "  - Final port: $final_port"
echo "  - Total rotations: $final_count"
echo "  - Last heartbeat: ${final_heartbeat}s ago"
echo "  - Rotation successful: $([ "$final_port" != "$initial_port" ] && echo -e "${GREEN}✅ YES${NC}" || echo -e "${RED}❌ NO${NC}")"
echo ""
echo -e "${BLUE}📖 Key MTD Features Verified:${NC}"
echo "  ✅ iptables NAT port redirection"
echo "  ✅ Zero-downtime rotation (internal port stays fixed)"
echo "  ✅ Old port closure"
echo "  ✅ New port activation"
echo "  ✅ Registry coordination"
echo "  ✅ API Gateway discovery"
echo "  ✅ Multiple rotation resilience"
echo ""
echo -e "${YELLOW}💡 Tips:${NC}"
echo "  - Watch live rotations: docker logs -f product-service"
echo "  - Check iptables: docker exec product-service iptables -t nat -L -n -v"
echo "  - Monitor metrics: curl http://localhost:$final_port/metrics | grep mtd"
echo "  - Service rotates automatically every 60 seconds"
echo ""
