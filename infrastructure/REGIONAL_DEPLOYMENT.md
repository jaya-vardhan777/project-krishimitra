# KrishiMitra Regional Deployment and Disaster Recovery

This document describes the multi-region deployment, failover, and disaster recovery capabilities of the KrishiMitra platform.

## Overview

The KrishiMitra platform implements comprehensive regional deployment and disaster recovery capabilities to ensure high availability and business continuity across multiple AWS regions.

**Requirements Addressed:**
- **11.3**: Regional uptime maintenance - 95% uptime across all supported regions
- **11.5**: Service quality during expansion - Onboard new regions without affecting existing service

## Architecture Components

### 1. Multi-Region Deployment

The platform supports deployment across multiple AWS regions:

- **Primary Region**: `ap-south-1` (Mumbai) - Main production region
- **Secondary Regions**: 
  - `ap-southeast-1` (Singapore)
  - `eu-west-1` (Ireland)

### 2. Health Monitoring

**Route 53 Health Checks:**
- HTTPS health checks on `/api/v1/health` endpoint
- 30-second check intervals
- 3 failure threshold before marking unhealthy
- Latency measurement enabled

**CloudWatch Monitoring:**
- Custom metrics for regional health status
- Health percentage tracking per region
- Overall system health composite metrics
- Automated alerting on degradation

### 3. Automated Failover

**Failover Triggers:**
- CloudWatch alarm state changes
- Health check failures
- Manual invocation for testing

**Failover Process:**
1. Detect primary region failure
2. Identify healthy secondary regions
3. Update Route 53 DNS records
4. Redirect traffic to healthy region
5. Send critical alerts
6. Log failover event for audit

### 4. Disaster Recovery

**Backup Strategy:**

**Production Environment:**
- Daily DynamoDB backups (30-day retention)
- Weekly backups (90-day retention, cold storage after 30 days)
- Monthly backups (1-year retention, cold storage after 60 days)
- Continuous backup enabled for point-in-time recovery

**Non-Production Environments:**
- Daily backups (7-day retention)

**Recovery Procedures:**
1. Identify latest recovery points
2. Restore DynamoDB tables
3. Restore S3 data
4. Verify data integrity
5. Update application configuration
6. Send recovery notifications

## Deployment

### Prerequisites

1. AWS CDK installed: `npm install -g aws-cdk`
2. Python 3.11+ installed
3. AWS credentials configured
4. Multiple AWS regions enabled in your account

### Configuration

Configure multi-region deployment in `cdk.context.json`:

```json
{
  "env": "prod",
  "account": "YOUR_AWS_ACCOUNT_ID",
  "region": "ap-south-1",
  "secondary_regions": ["ap-southeast-1", "eu-west-1"],
  "domain_name": "krishimitra.example.com",
  "alert_emails": [
    "ops-team@example.com",
    "devops@example.com"
  ]
}
```

### Deploy Regional Infrastructure

```bash
# Deploy to production with regional deployment
cd infrastructure
cdk deploy KrishiMitra-prod KrishiMitra-Regional-prod \
  --context env=prod \
  --context account=YOUR_ACCOUNT_ID \
  --context region=ap-south-1

# Deploy to staging
cdk deploy KrishiMitra-staging KrishiMitra-Regional-staging \
  --context env=staging
```

### Deploy Lambda Functions

The Lambda functions for failover, health monitoring, and disaster recovery are automatically deployed as part of the regional deployment stack.

## Operations

### Health Monitoring

Health monitoring runs automatically every 5 minutes via EventBridge:

```bash
# View health metrics in CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace KrishiMitra/Health \
  --metric-name RegionHealth \
  --dimensions Name=Environment,Value=prod Name=Region,Value=ap-south-1 \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T23:59:59Z \
  --period 300 \
  --statistics Average
```

### Manual Failover Testing

Test failover procedures without affecting production:

```bash
# Trigger manual failover test
aws events put-events \
  --entries '[{
    "Source": "aws.cloudwatch",
    "DetailType": "CloudWatch Alarm State Change",
    "Detail": "{\"alarmName\":\"KrishiMitra-Primary-Health-prod\",\"state\":{\"value\":\"ALARM\"}}"
  }]'
```

### Disaster Recovery

Initiate disaster recovery manually:

```bash
# Trigger disaster recovery
aws events put-events \
  --entries '[{
    "Source": "krishimitra.disaster-recovery",
    "DetailType": "Disaster Recovery Initiated",
    "Detail": "{\"recovery_type\":\"full\",\"target_region\":\"ap-southeast-1\"}"
  }]'
```

### View Recovery Points

```bash
# List available recovery points
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name krishimitra-backup-vault-prod
```

## Monitoring and Alerts

### SNS Topics

Two SNS topics are created for alerts:

1. **Critical Alerts** (`krishimitra-critical-alerts-{env}`)
   - Primary region failures
   - System-wide health issues
   - Disaster recovery failures
   - Requires immediate action

2. **Operational Alerts** (`krishimitra-operational-alerts-{env}`)
   - Secondary region degradation
   - Performance issues
   - Backup job failures
   - Informational notifications

### CloudWatch Dashboards

Access the regional health dashboard:

```
AWS Console → CloudWatch → Dashboards → KrishiMitra-{env}
```

Metrics available:
- Regional health status
- Health check latency
- Failover events
- Overall system health percentage

### CloudWatch Alarms

Key alarms configured:

1. **Primary Region Health** - Triggers on primary region failure
2. **Secondary Region Health** - Monitors secondary region status
3. **System Health Composite** - Overall system health across all regions

## Testing

### Health Check Testing

```bash
# Test health endpoint
curl https://api.krishimitra.example.com/api/v1/health

# Expected response:
{
  "status": "healthy",
  "region": "ap-south-1",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Failover Testing

1. Simulate primary region failure
2. Verify automatic failover to secondary region
3. Confirm DNS updates
4. Verify application functionality in secondary region
5. Test failback to primary region

### Disaster Recovery Testing

1. Create test backup
2. Initiate recovery to test environment
3. Verify data integrity
4. Validate application functionality
5. Document recovery time objective (RTO) and recovery point objective (RPO)

## Troubleshooting

### Failover Not Triggering

1. Check CloudWatch alarm status
2. Verify EventBridge rule is enabled
3. Check Lambda function logs
4. Verify IAM permissions

```bash
# View failover function logs
aws logs tail /aws/lambda/krishimitra-failover-prod --follow
```

### Recovery Job Failures

1. Check AWS Backup console for job status
2. Verify backup vault permissions
3. Check target region capacity
4. Review Lambda function logs

```bash
# View disaster recovery function logs
aws logs tail /aws/lambda/krishimitra-disaster-recovery-prod --follow
```

### Health Check Failures

1. Verify application is running
2. Check security group rules
3. Verify SSL certificate validity
4. Test health endpoint manually

## Best Practices

1. **Regular Testing**: Test failover and recovery procedures quarterly
2. **Monitor Metrics**: Review health metrics and alerts weekly
3. **Update Runbooks**: Keep disaster recovery procedures up to date
4. **Capacity Planning**: Ensure secondary regions have sufficient capacity
5. **Cost Optimization**: Review backup retention policies regularly
6. **Security**: Rotate IAM credentials and review permissions quarterly

## Cost Considerations

### Backup Costs

- DynamoDB backups: Pay per GB stored
- S3 backups: Standard storage rates
- Cold storage: Reduced rates after transition period

### Health Check Costs

- Route 53 health checks: $0.50 per health check per month
- CloudWatch metrics: Custom metrics pricing
- Lambda invocations: Free tier covers most usage

### Data Transfer Costs

- Cross-region data transfer for failover
- Backup replication costs
- Recovery data transfer

## Compliance

The regional deployment and disaster recovery implementation supports:

- **RTO (Recovery Time Objective)**: < 15 minutes
- **RPO (Recovery Point Objective)**: < 24 hours (daily backups)
- **Uptime SLA**: 95% across all regions (Requirement 11.3)
- **Data Residency**: Configurable per region
- **Audit Trail**: All failover and recovery events logged

## Support

For issues or questions:

1. Check CloudWatch logs and metrics
2. Review SNS alert notifications
3. Consult this documentation
4. Contact DevOps team via critical alerts topic

## References

- [AWS Backup Documentation](https://docs.aws.amazon.com/backup/)
- [Route 53 Health Checks](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/health-checks.html)
- [Multi-Region Architecture](https://aws.amazon.com/solutions/implementations/multi-region-application-architecture/)
- [Disaster Recovery on AWS](https://aws.amazon.com/disaster-recovery/)
