#!/usr/bin/env python3
"""
KrishiMitra AWS CDK Application Entry Point

This module serves as the main entry point for the KrishiMitra AWS CDK application.
It defines the CDK app and instantiates the necessary stacks for different environments.
"""

import aws_cdk as cdk
from stacks.krishimitra_stack import KrishiMitraStack

app = cdk.App()

# Get environment configuration from context or use defaults
env_name = app.node.try_get_context("env") or "dev"
account = app.node.try_get_context("account")
region = app.node.try_get_context("region") or "ap-south-1"

# Environment configuration
env = cdk.Environment(account=account, region=region)

# Create stack for the specified environment
KrishiMitraStack(
    app, 
    f"KrishiMitra-{env_name}",
    env=env,
    env_name=env_name,
    description=f"KrishiMitra AI Agricultural Platform - {env_name.upper()} Environment"
)

app.synth()