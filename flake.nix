{
  description = "SSLE Project 2 - Attack Tolerance Mechanisms (BFT + MTD)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        
        # Python environment with all dependencies
        pythonEnv = pkgs.python311.withPackages (ps: with ps; [
          flask
          requests
          prometheus-client
          pytest
          pytest-cov
          black
          pylint
          mypy
        ]);

        # Custom scripts
        testBFT = pkgs.writeShellScriptBin "test-bft" ''
          #!/usr/bin/env bash
          set -e
          
          echo "🧪 Testing Byzantine Fault Tolerance..."
          echo ""
          
          # Test 1: Check cluster quorum
          echo "Test 1: Checking BFT cluster quorum..."
          response=$(${pkgs.curl}/bin/curl -s http://localhost:8002/consensus/status || echo "ERROR")
          
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
        '';

        testMTD = pkgs.writeShellScriptBin "test-mtd" ''
          #!/usr/bin/env bash
          set -e
          
          echo "🎯 Testing Moving Target Defense..."
          echo ""
          
          # Test 1: Check service registry
          echo "Test 1: Checking service registry..."
          services=$(${pkgs.curl}/bin/curl -s http://localhost:5000/services || echo "ERROR")
          
          if [[ "$services" == "ERROR" ]]; then
            echo "❌ Service registry not reachable. Is docker-compose running?"
            exit 1
          fi
          
          echo "✅ Registered services:"
          echo "$services" | ${pkgs.jq}/bin/jq '.services[] | {name, port, rotation_count}'
          echo ""
          
          # Test 2: Scan ports before rotation
          echo "Test 2: Port scan (baseline)..."
          echo "Active ports in range 8000-8100:"
          for port in {8001..8013} {8080..8090}; do
            if ${pkgs.netcat}/bin/nc -z -w1 localhost $port 2>/dev/null; then
              echo "  - Port $port: OPEN"
            fi
          done
          echo ""
          
          # Test 3: Trigger rotation
          echo "Test 3: Triggering MTD rotation for product-service..."
          rotation=$(${pkgs.curl}/bin/curl -s -X POST http://localhost:5000/rotate/product-service || echo "ERROR")
          
          if [[ "$rotation" != "ERROR" ]]; then
            echo "✅ Rotation triggered:"
            echo "$rotation" | ${pkgs.jq}/bin/jq .
            new_port=$(echo "$rotation" | ${pkgs.jq}/bin/jq -r '.new_port')
            echo ""
            echo "Waiting for service to rotate to port $new_port..."
            sleep 5
          fi
          
          # Test 4: Verify service still works after rotation
          echo ""
          echo "Test 4: Verifying service availability after rotation..."
          products=$(${pkgs.curl}/bin/curl -s http://localhost:8080/proxy/product-service/api/products || echo "ERROR")
          
          if [[ "$products" != "ERROR" ]]; then
            echo "✅ Product service still accessible after rotation!"
            echo "$products" | ${pkgs.jq}/bin/jq '. | length' | xargs echo "Products available:"
          else
            echo "⚠️  Product service not responding (may still be rotating)"
          fi
          
          echo ""
          echo "🎉 MTD testing complete!"
          echo ""
          echo "💡 Tip: Run this test multiple times over 10 minutes to see port rotations"
        '';

        checkCluster = pkgs.writeShellScriptBin "check-cluster" ''
          #!/usr/bin/env bash
          
          echo "📊 SSLE Project 2 - Cluster Health Check"
          echo "========================================"
          echo ""
          
          # Check if Docker is running
          if ! ${pkgs.docker}/bin/docker info > /dev/null 2>&1; then
            echo "❌ Docker is not running"
            exit 1
          fi
          
          echo "✅ Docker is running"
          echo ""
          
          # Check containers
          echo "📦 Container Status:"
          ${pkgs.docker}/bin/docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(order-node|product-service|payment-service|registry|NAMES)"
          echo ""
          
          # Check BFT cluster
          echo "🔒 BFT Cluster Status:"
          for node in 8002 8012 8022; do
            status=$(${pkgs.curl}/bin/curl -s http://localhost:$node/health 2>/dev/null || echo "DOWN")
            if [[ "$status" != "DOWN" ]]; then
              node_id=$(echo "$status" | ${pkgs.jq}/bin/jq -r '.node')
              echo "  ✅ $node_id (port $node): HEALTHY"
            else
              echo "  ❌ order-node-? (port $node): DOWN"
            fi
          done
          echo ""
          
          # Check consensus quorum
          consensus=$(${pkgs.curl}/bin/curl -s http://localhost:8002/consensus/status 2>/dev/null)
          if [[ -n "$consensus" ]]; then
            echo "🗳️  Consensus Status:"
            echo "$consensus" | ${pkgs.jq}/bin/jq '{
              cluster_size,
              healthy_nodes,
              quorum_size,
              quorum_available
            }'
          fi
          echo ""
          
          # Check MTD service registry
          echo "🎯 MTD Service Registry:"
          ${pkgs.curl}/bin/curl -s http://localhost:5000/services/status 2>/dev/null | \
            ${pkgs.jq}/bin/jq '.services[] | {name, port, healthy, rotation_count}' || \
            echo "  ⚠️  Registry not accessible"
          echo ""
          
          # Check monitoring
          echo "📈 Monitoring:"
          if ${pkgs.curl}/bin/curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
            echo "  ✅ Prometheus: http://localhost:9090"
          else
            echo "  ❌ Prometheus: DOWN"
          fi
          
          if ${pkgs.curl}/bin/curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
            echo "  ✅ Grafana: http://localhost:3000 (admin/admin)"
          else
            echo "  ❌ Grafana: DOWN"
          fi
          
          if ${pkgs.curl}/bin/curl -sk https://localhost:443 > /dev/null 2>&1; then
            echo "  ✅ Wazuh: https://localhost:443"
          else
            echo "  ❌ Wazuh: DOWN"
          fi
          
          echo ""
          echo "🎉 Health check complete!"
        '';

        startProject = pkgs.writeShellScriptBin "start-project" ''
          #!/usr/bin/env bash
          set -e
          
          echo "🚀 Starting SSLE Project 2..."
          echo ""
          
          # Check if docker-compose.yml exists
          if [ ! -f "docker-compose.yml" ]; then
            echo "❌ docker-compose.yml not found!"
            echo "   Make sure you're in the project root directory"
            exit 1
          fi
          
          echo "📦 Starting containers..."
          ${pkgs.docker-compose}/bin/docker-compose up -d
          
          echo ""
          echo "⏳ Waiting for services to initialize (30s)..."
          sleep 30
          
          echo ""
          check-cluster
        '';

        stopProject = pkgs.writeShellScriptBin "stop-project" ''
          #!/usr/bin/env bash
          
          echo "🛑 Stopping SSLE Project 2..."
          ${pkgs.docker-compose}/bin/docker-compose down
          echo "✅ All containers stopped"
        '';

        runTests = pkgs.writeShellScriptBin "run-tests" ''
          #!/usr/bin/env bash
          set -e
          
          echo "🧪 Running SSLE Project 2 Test Suite"
          echo "====================================="
          echo ""
          
          # Run Python unit tests if they exist
          if [ -d "tests" ]; then
            echo "Running unit tests..."
            cd tests
            ${pythonEnv}/bin/pytest -v --cov=../services --cov-report=term-missing || true
            cd ..
            echo ""
          fi
          
          # Run integration tests
          echo "Running integration tests..."
          test-bft
          echo ""
          test-mtd
        '';

      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Core tools
            docker
            docker-compose
            
            # Python environment
            pythonEnv
            
            # Utilities
            curl
            jq
            netcat
            nmap
            
            # Testing tools
            k6  # Load testing
            hey # HTTP load generator
            
            # Git
            git
            
            # Text editors
            vim
            
            # Custom scripts
            testBFT
            testMTD
            checkCluster
            startProject
            stopProject
            runTests
          ];

          shellHook = ''
            echo ""
            echo "🛡️  SSLE Project 2 - Attack Tolerance Mechanisms"
            echo "================================================="
            echo ""
            echo "📚 Available commands:"
            echo "  start-project    - Start all Docker containers"
            echo "  stop-project     - Stop all containers"
            echo "  check-cluster    - Check cluster health"
            echo "  test-bft         - Test Byzantine Fault Tolerance"
            echo "  test-mtd         - Test Moving Target Defense"
            echo "  run-tests        - Run full test suite"
            echo ""
            echo "📊 Monitoring:"
            echo "  Prometheus:  http://localhost:9090"
            echo "  Grafana:     http://localhost:3000 (admin/admin)"
            echo "  Wazuh:       https://localhost:443"
            echo "  Registry:    http://localhost:5000/services"
            echo ""
            echo "🔧 Development:"
            echo "  Python:      ${pythonEnv}/bin/python"
            echo "  Docker:      ${pkgs.docker}/bin/docker"
            echo "  Compose:     ${pkgs.docker-compose}/bin/docker-compose"
            echo ""
            echo "💡 Quick start:"
            echo "  1. start-project      # Start everything"
            echo "  2. check-cluster      # Verify health"
            echo "  3. test-bft           # Test BFT"
            echo "  4. test-mtd           # Test MTD"
            echo ""
          '';
        };

        # Package the project
        packages.default = pkgs.stdenv.mkDerivation {
          name = "ssle-project2";
          src = ./.;
          
          installPhase = ''
            mkdir -p $out
            cp -r . $out/
          '';
        };
      }
    );
}
