#!/usr/bin/env python3
"""
Byzantine Fault Tolerance Consensus Module with Vault Authentication

Implements a simple BFT consensus protocol:
- Leader proposes operations
- All replicas vote
- 2f+1 agreement required (where f=1, so need 2/3 nodes)
- State replication across nodes
- Node authentication using Vault tokens
"""

import hashlib
import hmac
import json
import logging
import os
import sys
import time
from threading import Lock
from typing import Dict, List, Optional

import requests

# Add parent directory to path for vault_client import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vault_client import vault_client

logger = logging.getLogger(__name__)


class BFTConsensus:
    def __init__(self, node_id: str, cluster_nodes: List[str]):
        """
        Initialize BFT consensus module
        
        Args:
            node_id: This node's identifier (e.g., "order-node-1:8002")
            cluster_nodes: List of all cluster node URLs
        """
        self.node_id = node_id
        self.cluster_nodes = cluster_nodes
        self.cluster_size = len(cluster_nodes)
        self.quorum_size = (2 * self.cluster_size) // 3 + 1  # 2f+1 where f = (n-1)//3
        
        # Get authentication token from Vault
        node_name = node_id.split(':')[0]  # Extract 'order-node-1' from 'order-node-1:8002'
        self.auth_token = vault_client.get_bft_node_token(node_name)
        
        if self.auth_token:
            logger.info(f"Node authentication token loaded from Vault for {node_name}")
        else:
            logger.warning(f"No Vault token for {node_name} - authentication disabled")
        
        # Consensus state
        self.pending_operations = {}  # {operation_id: {data, votes, status}}
        self.operations_lock = Lock()
        
        logger.info(f"BFT Consensus initialized: {node_id}")
        logger.info(f"Cluster: {cluster_nodes}")
        logger.info(f"Quorum: {self.quorum_size}/{self.cluster_size}")
        logger.info(f"Vault authentication: {'enabled' if self.auth_token else 'disabled'}")
    
    def _sign_vote(self, operation_id: str, vote: str) -> str:
        """
        Sign a vote using node's authentication token
        
        Args:
            operation_id: Operation ID being voted on
            vote: Vote value ('approve' or 'reject')
        
        Returns:
            str: HMAC signature of vote
        """
        if not self.auth_token:
            return "no-auth"  # No authentication when Vault disabled
        
        message = f"{operation_id}:{vote}:{self.node_id}"
        signature = hmac.new(
            self.auth_token.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _verify_vote_signature(self, node_id: str, operation_id: str, vote: str, signature: str) -> bool:
        """
        Verify a vote signature from another node
        
        Args:
            node_id: Node that cast the vote
            operation_id: Operation ID
            vote: Vote value
            signature: Vote signature to verify
        
        Returns:
            bool: True if signature is valid
        """
        if signature == "no-auth":
            # No authentication - allow vote (dev mode)
            return True
        
        # Get the node's token from Vault
        node_name = node_id.split(':')[0]
        node_token = vault_client.get_bft_node_token(node_name)
        
        if not node_token:
            logger.warning(f"Cannot verify vote from {node_id} - no token in Vault")
            return True  # Allow if Vault unavailable (graceful degradation)
        
        # Compute expected signature
        message = f"{operation_id}:{vote}:{node_id}"
        expected_signature = hmac.new(
            node_token.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if signature != expected_signature:
            logger.error(f"BYZANTINE BEHAVIOR DETECTED: Invalid vote signature from {node_id}")
            logger.error(f"  Expected: {expected_signature[:16]}...")
            logger.error(f"  Received: {signature[:16]}...")
            return False
        
        return True
    
    def propose_operation(self, operation_type: str, operation_data: dict) -> dict:
        """
        Propose an operation to the cluster
        
        Args:
            operation_type: Type of operation (e.g., "CREATE_ORDER")
            operation_data: Operation data
        
        Returns:
            dict: {"success": bool, "operation_id": str, "votes": dict}
        """
        # Create operation ID
        operation_id = self._generate_operation_id(operation_type, operation_data)
        
        logger.info(f"Proposing operation {operation_id}: {operation_type}")
        
        # Initialize operation tracking
        with self.operations_lock:
            self.pending_operations[operation_id] = {
                "type": operation_type,
                "data": operation_data,
                "votes": {},
                "status": "pending",
                "proposed_at": time.time(),
                "proposer": self.node_id,
            }
        
        # Request votes from all nodes
        votes = self._request_votes(operation_id, operation_type, operation_data)
        
        # Verify vote signatures and count valid votes
        valid_votes = {}
        for node, vote_info in votes.items():
            if isinstance(vote_info, dict):
                vote = vote_info.get("vote")
                signature = vote_info.get("signature")
                
                if self._verify_vote_signature(node, operation_id, vote, signature):
                    valid_votes[node] = vote
                else:
                    logger.warning(f"Rejected invalid vote from {node}")
                    valid_votes[node] = "invalid_signature"
            else:
                valid_votes[node] = vote_info
        
        # Count approved votes (only valid signatures)
        approved_count = sum(1 for vote in valid_votes.values() if vote == "approve")
        
        # Update operation status
        with self.operations_lock:
            if operation_id in self.pending_operations:
                self.pending_operations[operation_id]["votes"] = valid_votes
                
                if approved_count >= self.quorum_size:
                    self.pending_operations[operation_id]["status"] = "committed"
                    logger.info(f"Operation {operation_id} COMMITTED ({approved_count}/{self.cluster_size} valid votes)")
                    return {
                        "success": True,
                        "operation_id": operation_id,
                        "votes": valid_votes,
                        "approved": approved_count,
                        "quorum": self.quorum_size,
                    }
                else:
                    self.pending_operations[operation_id]["status"] = "rejected"
                    logger.warning(f"Operation {operation_id} REJECTED ({approved_count}/{self.cluster_size} valid votes, need {self.quorum_size})")
                    return {
                        "success": False,
                        "operation_id": operation_id,
                        "votes": valid_votes,
                        "approved": approved_count,
                        "quorum": self.quorum_size,
                        "reason": "quorum not reached",
                    }
    
    def _request_votes(self, operation_id: str, operation_type: str, operation_data: dict) -> Dict[str, dict]:
        """
        Request votes from all cluster nodes
        
        Returns:
            dict: {node_id: {"vote": "approve"|"reject", "signature": "..."}}
        """
        votes = {}
        
        for node_url in self.cluster_nodes:
            try:
                response = requests.post(
                    f"{node_url}/consensus/vote",
                    json={
                        "operation_id": operation_id,
                        "operation_type": operation_type,
                        "operation_data": operation_data,
                        "proposer": self.node_id,
                    },
                    timeout=5,
                )
                
                if response.status_code == 200:
                    vote_data = response.json()
                    votes[vote_data["node"]] = {
                        "vote": vote_data["vote"],
                        "signature": vote_data.get("signature", "no-auth"),
                    }
                    logger.debug(f"Vote from {vote_data['node']}: {vote_data['vote']}")
                else:
                    logger.warning(f"Failed to get vote from {node_url}: {response.status_code}")
                    votes[node_url] = "unreachable"
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Error getting vote from {node_url}: {e}")
                votes[node_url] = "unreachable"
        
        return votes
    
    def validate_and_vote(self, operation_id: str, operation_type: str, operation_data: dict, proposer: str) -> tuple:
        """
        Validate an operation and return vote with signature
        
        Args:
            operation_id: Operation identifier
            operation_type: Type of operation
            operation_data: Operation data
            proposer: Node that proposed the operation
        
        Returns:
            tuple: (vote: str, signature: str)
        """
        logger.info(f"Validating operation {operation_id} from {proposer}")
        
        # Validation logic
        try:
            if operation_type == "CREATE_ORDER":
                vote = self._validate_create_order(operation_data)
            elif operation_type == "UPDATE_STATUS":
                vote = self._validate_update_status(operation_data)
            elif operation_type == "CANCEL_ORDER":
                vote = self._validate_cancel_order(operation_data)
            else:
                logger.warning(f"Unknown operation type: {operation_type}")
                vote = "reject"
        
        except Exception as e:
            logger.error(f"Validation error: {e}")
            vote = "reject"
        
        # Sign the vote
        signature = self._sign_vote(operation_id, vote)
        
        return vote, signature
    
    def _validate_create_order(self, data: dict) -> str:
        """Validate order creation"""
        required_fields = ["customer_id", "items"]
        
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing required field: {field}")
                return "reject"
        
        if not isinstance(data["items"], list) or len(data["items"]) == 0:
            logger.warning("Invalid items list")
            return "reject"
        
        # Validate each item
        for item in data["items"]:
            if "product_id" not in item or "quantity" not in item:
                logger.warning(f"Invalid item: {item}")
                return "reject"
            
            if item["quantity"] <= 0:
                logger.warning(f"Invalid quantity: {item['quantity']}")
                return "reject"
        
        return "approve"
    
    def _validate_update_status(self, data: dict) -> str:
        """Validate status update"""
        if "order_id" not in data or "status" not in data:
            return "reject"
        
        valid_statuses = ["pending", "processing", "shipped", "delivered", "cancelled"]
        if data["status"] not in valid_statuses:
            return "reject"
        
        return "approve"
    
    def _validate_cancel_order(self, data: dict) -> str:
        """Validate order cancellation"""
        if "order_id" not in data:
            return "reject"
        
        return "approve"
    
    def _generate_operation_id(self, operation_type: str, operation_data: dict) -> str:
        """Generate unique operation ID"""
        timestamp = str(time.time())
        data_str = json.dumps(operation_data, sort_keys=True)
        hash_input = f"{operation_type}:{data_str}:{timestamp}:{self.node_id}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    def get_cluster_status(self) -> dict:
        """Get current cluster status"""
        healthy_nodes = 0
        node_statuses = []
        
        for node_url in self.cluster_nodes:
            try:
                response = requests.get(f"{node_url}/health", timeout=2)
                if response.status_code == 200:
                    healthy_nodes += 1
                    node_statuses.append({"node": node_url, "status": "healthy"})
                else:
                    node_statuses.append({"node": node_url, "status": "unhealthy"})
            except:
                node_statuses.append({"node": node_url, "status": "unreachable"})
        
        quorum_available = healthy_nodes >= self.quorum_size
        
        return {
            "cluster_size": self.cluster_size,
            "healthy_nodes": healthy_nodes,
            "quorum_size": self.quorum_size,
            "quorum_available": quorum_available,
            "nodes": node_statuses,
            "vault_auth_enabled": bool(self.auth_token),
        }
    
    def get_operation_status(self, operation_id: str) -> Optional[dict]:
        """Get status of a specific operation"""
        with self.operations_lock:
            return self.pending_operations.get(operation_id)
