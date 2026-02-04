#!/usr/bin/env python3
"""
Deployment script for KrishiMitra Platform.

This script handles the deployment of the KrishiMitra platform to different environments
using AWS CDK with proper environment configuration and validation.
"""

import argparse
import os
import subprocess
import sys
from typing import Dict, Any, Optional


def run_command(command: str, cwd: Optional[str] = None) -> int:
    """Run a shell command and return the exit code."""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, cwd=cwd)
    return result.returncode


def validate_environment(env: str) -> bool:
    """Validate that the environment is supported."""
    supported_envs = ["dev", "staging", "prod"]
    if env not in supported_envs:
        print(f"Error: Environment '{env}' not supported. Use one of: {supported_envs}")
        return False
    return True


def check_prerequisites() -> bool:
    """Check that all prerequisites are installed."""
    prerequisites = [
        ("python", "Python 3.11+"),
        ("node", "Node.js 18+"),
        ("npm", "npm"),
        ("aws", "AWS CLI"),
        ("cdk", "AWS CDK CLI")
    ]
    
    missing = []
    for cmd, description in prerequisites:
        if run_command(f"which {cmd} > /dev/null 2>&1") != 0:
            missing.append(description)
    
    if missing:
        print("Error: Missing prerequisites:")
        for item in missing:
            print(f"  - {item}")
        return False
    
    return True


def install_dependencies() -> bool:
    """Install Python and CDK dependencies."""
    print("Installing Python dependencies...")
    if run_command("pip install -r requirements.txt") != 0:
        print("Error: Failed to install Python dependencies")
        return False
    
    print("Installing CDK dependencies...")
    if run_command("pip install -r infrastructure/requirements.txt") != 0:
        print("Error: Failed to install CDK dependencies")
        return False
    
    return True


def bootstrap_cdk(env: str, region: str, account: str) -> bool:
    """Bootstrap CDK for the target environment."""
    print(f"Bootstrapping CDK for {env} environment...")
    
    bootstrap_cmd = f"cdk bootstrap aws://{account}/{region} --context env={env}"
    if run_command(bootstrap_cmd, cwd="infrastructure") != 0:
        print("Error: CDK bootstrap failed")
        return False
    
    return True


def deploy_infrastructure(env: str, region: str, account: str) -> bool:
    """Deploy the infrastructure using CDK."""
    print(f"Deploying infrastructure for {env} environment...")
    
    deploy_cmd = f"cdk deploy --context env={env} --context region={region} --context account={account} --require-approval never"
    if run_command(deploy_cmd, cwd="infrastructure") != 0:
        print("Error: Infrastructure deployment failed")
        return False
    
    return True


def package_lambda_code() -> bool:
    """Package the Lambda function code."""
    print("Packaging Lambda function code...")
    
    # Create deployment package
    if run_command("rm -rf dist && mkdir -p dist") != 0:
        return False
    
    # Copy source code
    if run_command("cp -r src/krishimitra dist/") != 0:
        return False
    
    # Install dependencies in the package
    if run_command("pip install -r requirements.txt -t dist/") != 0:
        return False
    
    print("Lambda code packaged successfully")
    return True


def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(description="Deploy KrishiMitra Platform")
    parser.add_argument("environment", choices=["dev", "staging", "prod"], 
                       help="Target environment")
    parser.add_argument("--region", default="ap-south-1", 
                       help="AWS region (default: ap-south-1)")
    parser.add_argument("--account", required=True, 
                       help="AWS account ID")
    parser.add_argument("--skip-deps", action="store_true", 
                       help="Skip dependency installation")
    parser.add_argument("--skip-bootstrap", action="store_true", 
                       help="Skip CDK bootstrap")
    
    args = parser.parse_args()
    
    # Validate environment
    if not validate_environment(args.environment):
        sys.exit(1)
    
    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)
    
    # Install dependencies
    if not args.skip_deps:
        if not install_dependencies():
            sys.exit(1)
    
    # Package Lambda code
    if not package_lambda_code():
        sys.exit(1)
    
    # Bootstrap CDK
    if not args.skip_bootstrap:
        if not bootstrap_cdk(args.environment, args.region, args.account):
            sys.exit(1)
    
    # Deploy infrastructure
    if not deploy_infrastructure(args.environment, args.region, args.account):
        sys.exit(1)
    
    print(f"✅ Successfully deployed KrishiMitra to {args.environment} environment!")
    print(f"Region: {args.region}")
    print(f"Account: {args.account}")
    
    # Get stack outputs
    print("\nRetrieving stack outputs...")
    outputs_cmd = f"cdk outputs --context env={args.environment}"
    run_command(outputs_cmd, cwd="infrastructure")


if __name__ == "__main__":
    main()