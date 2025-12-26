#!/usr/bin/env python3
"""
Vault Client Utility

Simple Vault client for retrieving secrets from HashiCorp Vault
"""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class VaultClient:
    def __init__(self, vault_addr: str = None, vault_token: str = None):
        """
        Initialize Vault client
        
        Args:
            vault_addr: Vault server address (default: from VAULT_ADDR env)
            vault_token: Vault token (default: from VAULT_TOKEN env)
        """
        self.vault_addr = vault_addr or os.environ.get("VAULT_ADDR", "http://vault:8200")
        self.vault_token = vault_token or os.environ.get("VAULT_TOKEN", "")
        self.enabled = bool(self.vault_token)
        
        if not self.enabled:
            logger.warning("Vault client initialized but no token provided - Vault disabled")
        else:
            logger.info(f"Vault client initialized: {self.vault_addr}")
    
    def read_secret(self, path: str) -> Optional[dict]:
        """
        Read a secret from Vault
        
        Args:
            path: Secret path (e.g., 'bft-cluster/order-node-1')
        
        Returns:
            dict: Secret data or None if not found/error
        """
        if not self.enabled:
            logger.debug("Vault disabled, skipping secret read")
            return None
        
        try:
            url = f"{self.vault_addr}/v1/secret/data/{path}"
            headers = {"X-Vault-Token": self.vault_token}
            
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("data", {})
            else:
                logger.error(f"Failed to read secret {path}: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"Error reading secret from Vault: {e}")
            return None
    
    def get_bft_node_token(self, node_id: str) -> Optional[str]:
        """
        Get BFT node authentication token
        
        Args:
            node_id: Node identifier (e.g., 'order-node-1')
        
        Returns:
            str: Authentication token or None
        """
        secret = self.read_secret(f"bft-cluster/{node_id}")
        if secret:
            return secret.get("auth_token")
        return None
    
    def get_service_token(self, service_name: str) -> Optional[str]:
        """
        Get service authentication token
        
        Args:
            service_name: Service name (e.g., 'product-service')
        
        Returns:
            str: Service token or None
        """
        secret = self.read_secret(f"services/{service_name}")
        if secret:
            return secret.get("service_token")
        return None
    
    def get_registry_token(self) -> Optional[str]:
        """
        Get Service Registry API token
        
        Returns:
            str: Registry token or None
        """
        secret = self.read_secret("registry/api-token")
        if secret:
            return secret.get("api_token")
        return None
    
    def verify_token(self, token: str, expected_token: str) -> bool:
        """
        Verify a token matches expected value
        
        Args:
            token: Token to verify
            expected_token: Expected token value
        
        Returns:
            bool: True if tokens match
        """
        if not self.enabled:
            # If Vault disabled, allow all tokens (dev mode)
            return True
        
        return token == expected_token


# Global Vault client instance
vault_client = VaultClient()
