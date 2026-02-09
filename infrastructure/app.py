#!/usr/bin/env python3
"""
KrishiMitra AWS CDK Application Entry Point

This module serves as the main entry point for the KrishiMitra AWS CDK application.
It defines the CDK app and instantiates the necessary stacks for different environments.
"""

import aws_cdk as cdk
from stacks.krishimitra_stack import KrishiMitraStack
from stacks.regional_deployment_stack import RegionalDeploymentStack

app = cdk.App()

# Get environment configuration from context or use defaults
env_name = app.node.try_get_context("env") or "dev"
account = app.node.try_get_context("account")
region = app.node.try_get_context("region") or "ap-south-1"

# Multi-region configuration
primary_region = region
secondary_regions = app.node.try_get_context("secondary_regions") or ["ap-southeast-1", "eu-west-1"]
domain_name = app.node.try_get_context("domain_name")

# Environment configuration
env = cdk.Environment(account=account, region=region)

# Create main stack for the specified environment
main_stack = KrishiMitraStack(
    app, 
    f"KrishiMitra-{env_name}",
    env=env,
    env_name=env_name,
    description=f"KrishiMitra AI Agricultural Platform - {env_name.upper()} Environment"
)

# Create regional deployment stack for production and staging
if env_name in ["prod", "staging"]:
    regional_stack = RegionalDeploymentStack(
        app,
        f"KrishiMitra-Regional-{env_name}",
        env=env,
        env_name=env_name,
        primary_region=primary_region,
        secondary_regions=secondary_regions,
        domain_name=domain_name,
        description=f"KrishiMitra Regional Deployment and DR - {env_name.upper()} Environment"
    )
    
    # Add dependency to ensure main stack is created first
    regional_stack.add_dependency(main_stack)

app.synth()