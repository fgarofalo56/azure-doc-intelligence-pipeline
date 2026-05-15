# Disaster Recovery Guide

> **Comprehensive guide for backup, recovery, and business continuity for the Azure Document Intelligence Pipeline**

---

## Overview

This guide covers disaster recovery (DR) procedures for the Azure Document Intelligence Pipeline, including:

- Cosmos DB backup and restore procedures
- Blob Storage recovery options
- Point-in-time restore (PITR)
- Geo-replication configuration
- Recovery time objectives (RTO) and recovery point objectives (RPO)

---

## Cosmos DB Backup Options

The pipeline supports two backup policy types, configured via Bicep parameters:

### Periodic Backup (Default for Dev)

Periodic backup takes snapshots at regular intervals. Best for development and non-critical workloads.

```bicep
// In infra/parameters/dev.bicepparam
param backupPolicyType = 'Periodic'
param backupIntervalInMinutes = 240        // Every 4 hours
param backupRetentionIntervalInHours = 8   // Keep for 8 hours
param backupStorageRedundancy = 'Local'    // Local redundancy
```

**Characteristics:**
- **RPO**: 4-24 hours (depends on backup interval)
- **RTO**: Hours to days (manual restore via Azure support)
- **Cost**: Lower storage costs
- **Restore**: Contact Azure support for restore

| Parameter | Dev Default | Prod Default | Range |
|-----------|-------------|--------------|-------|
| `backupIntervalInMinutes` | 240 (4 hrs) | 240 (4 hrs) | 60-1440 |
| `backupRetentionIntervalInHours` | 8 | 168 (1 week) | 8-720 |
| `backupStorageRedundancy` | Local | Geo | Local, Zone, Geo |

### Continuous Backup (Recommended for Prod)

Continuous backup enables point-in-time restore (PITR) with granular recovery. Best for production workloads requiring low RPO.

```bicep
// In infra/parameters/prod.bicepparam
param backupPolicyType = 'Continuous'
param continuousBackupTier = 'Continuous30Days'  // 30-day retention
```

**Characteristics:**
- **RPO**: Near-zero (seconds)
- **RTO**: Minutes to hours (self-service restore)
- **Cost**: Higher storage costs
- **Restore**: Self-service via Azure Portal or CLI

| Tier | Retention | Use Case |
|------|-----------|----------|
| `Continuous7Days` | 7 days | Dev/test with PITR needs |
| `Continuous30Days` | 30 days | Production workloads |

---

## Point-in-Time Restore (PITR)

When using Continuous backup, you can restore to any point within the retention period.

### Prerequisites

- Cosmos DB account with Continuous backup enabled
- Sufficient permissions (Cosmos DB Account Reader + Contributor)

### Restore via Azure Portal

1. Navigate to your Cosmos DB account in Azure Portal
2. Select **Point in Time Restore** under Settings
3. Choose restore point (timestamp)
4. Select target resource group and account name
5. Click **Submit** to start restore

### Restore via Azure CLI

```bash
# List available restore timestamps
az cosmosdb restorable-database-account list \
  --name <cosmos-account-name> \
  --location <location>

# Restore to a specific point in time
az cosmosdb restore \
  --target-database-account-name <new-account-name> \
  --source-database-account-name <source-account-name> \
  --restore-timestamp "2024-01-15T10:30:00Z" \
  --location <location> \
  --resource-group <resource-group>
```

### Restore via PowerShell

```powershell
# Restore Cosmos DB to point in time
Restore-AzCosmosDBAccount `
    -TargetResourceGroupName "rg-restored" `
    -TargetDatabaseAccountName "cosmos-restored" `
    -SourceDatabaseAccountName "cosmos-original" `
    -RestoreTimestampInUtc "2024-01-15T10:30:00Z" `
    -Location "eastus"
```

---

## Geo-Replication

For high availability and disaster recovery across regions, enable geo-replication.

### Configuration

```bicep
// Enable geo-replication in Bicep
param enableGeoReplication = true
param secondaryLocation = 'westus2'
param enableZoneRedundancy = true
```

**Characteristics:**
- **Automatic failover**: Cosmos DB automatically fails over to secondary region
- **Multi-region reads**: Read from closest region for lower latency
- **RPO**: Near-zero (synchronous replication)
- **RTO**: Minutes (automatic failover)

### Manual Failover

```bash
# Trigger manual failover to secondary region
az cosmosdb failover-priority-change \
  --name <cosmos-account-name> \
  --resource-group <resource-group> \
  --failover-policies "westus2=0" "eastus=1"
```

### Check Replication Status

```bash
# View current replication configuration
az cosmosdb show \
  --name <cosmos-account-name> \
  --resource-group <resource-group> \
  --query "{locations: locations, enableAutomaticFailover: enableAutomaticFailover}"
```

---

## Blob Storage Recovery

### Soft Delete

Blob Storage soft delete allows recovery of deleted blobs within the retention period.

```bash
# Enable soft delete (if not already enabled via Bicep)
az storage blob service-properties delete-policy update \
  --account-name <storage-account> \
  --enable true \
  --days-retained 14

# List deleted blobs
az storage blob list \
  --account-name <storage-account> \
  --container-name pdfs \
  --include d  # Include deleted blobs

# Restore a deleted blob
az storage blob undelete \
  --account-name <storage-account> \
  --container-name pdfs \
  --name "incoming/document.pdf"
```

### Blob Versioning

Enable versioning to keep previous versions of blobs:

```bash
# Restore previous version
az storage blob copy start \
  --account-name <storage-account> \
  --destination-container pdfs \
  --destination-blob "incoming/document.pdf" \
  --source-uri "https://<storage-account>.blob.core.windows.net/pdfs/incoming/document.pdf?versionid=<version-id>"
```

---

## Recovery Procedures

### Scenario 1: Accidental Data Deletion

**Cosmos DB (Continuous Backup):**
1. Identify the timestamp before deletion
2. Perform point-in-time restore to new account
3. Validate restored data
4. Update application connection strings

**Blob Storage:**
1. Use soft delete to restore deleted blobs
2. Or restore from blob versioning

### Scenario 2: Regional Outage

**With Geo-Replication:**
1. Automatic failover triggers (if enabled)
2. Manual failover if automatic is disabled:
   ```bash
   az cosmosdb failover-priority-change \
     --name <cosmos-account-name> \
     --resource-group <resource-group> \
     --failover-policies "<secondary-region>=0" "<primary-region>=1"
   ```
3. Verify application connectivity
4. Monitor for primary region recovery

**Without Geo-Replication:**
1. Wait for regional recovery
2. Or restore from latest backup (if periodic backup enabled)

### Scenario 3: Data Corruption

1. Identify when corruption occurred
2. Restore to point-in-time before corruption (Continuous) or latest clean backup (Periodic)
3. Re-process any documents uploaded after restore point
4. Validate data integrity

---

## Recovery Time Objectives (RTO) and Recovery Point Objectives (RPO)

| Scenario | Backup Type | RPO | RTO |
|----------|-------------|-----|-----|
| Dev/Test | Periodic (Local) | 4-24 hours | Hours-Days |
| Production | Continuous (30-day) | Seconds | Minutes-Hours |
| Production + Geo | Continuous + Multi-region | Near-zero | Minutes |

### Recommended Production Configuration

```bicep
// Production DR configuration
param environment = 'prod'
param backupPolicyType = 'Continuous'
param continuousBackupTier = 'Continuous30Days'
param enableGeoReplication = true
param secondaryLocation = 'westus2'          // Different region
param enableZoneRedundancy = true            // Zone redundancy
param backupStorageRedundancy = 'Geo'        // For any periodic components
```

---

## Testing Disaster Recovery

### Regular DR Drills

1. **Monthly**: Test point-in-time restore to non-production environment
2. **Quarterly**: Test manual failover to secondary region (in DR environment)
3. **Annually**: Full DR drill with stakeholder involvement

### Validation Checklist

- [ ] Restore completes within expected RTO
- [ ] Data integrity verified (document count, sample validation)
- [ ] Application can connect to restored resources
- [ ] All extracted documents are accessible
- [ ] Processing pipeline functions correctly
- [ ] Monitoring and alerts are operational

### Sample DR Test Script

```bash
#!/bin/bash
# DR Test Script - Cosmos DB Point-in-Time Restore

TIMESTAMP=$(date -u -d "1 hour ago" +"%Y-%m-%dT%H:%M:%SZ")
SOURCE_ACCOUNT="cosmos-prod"
TARGET_ACCOUNT="cosmos-dr-test-$(date +%s)"
RESOURCE_GROUP="rg-dr-test"
LOCATION="eastus"

echo "Starting DR test restore to $TARGET_ACCOUNT"
echo "Restore point: $TIMESTAMP"

# Create target resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Perform restore
az cosmosdb restore \
  --target-database-account-name $TARGET_ACCOUNT \
  --source-database-account-name $SOURCE_ACCOUNT \
  --restore-timestamp $TIMESTAMP \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP

# Validate document count
ORIGINAL_COUNT=$(az cosmosdb sql query \
  --name $SOURCE_ACCOUNT \
  --database-name DocumentsDB \
  --container-name ExtractedDocuments \
  --query "SELECT VALUE COUNT(1) FROM c" \
  --query-text "SELECT VALUE COUNT(1) FROM c" \
  -o tsv)

RESTORED_COUNT=$(az cosmosdb sql query \
  --name $TARGET_ACCOUNT \
  --database-name DocumentsDB \
  --container-name ExtractedDocuments \
  --query-text "SELECT VALUE COUNT(1) FROM c" \
  -o tsv)

echo "Original count: $ORIGINAL_COUNT"
echo "Restored count: $RESTORED_COUNT"

# Cleanup (optional)
# az group delete --name $RESOURCE_GROUP --yes --no-wait
```

---

## Monitoring and Alerts

### Key Metrics to Monitor

| Metric | Threshold | Action |
|--------|-----------|--------|
| Backup completion | Failure | Alert + investigate |
| Replication lag | > 5 seconds | Alert + check network |
| Failover events | Any | Notify operations |
| Storage soft delete usage | > 80% retention | Review deletion patterns |

### Azure Monitor Alerts

```bash
# Create alert for backup failures
az monitor metrics alert create \
  --name "CosmosDB-Backup-Failed" \
  --resource-group <resource-group> \
  --scopes <cosmos-resource-id> \
  --condition "count BackupStorageUsage < 1" \
  --window-size 24h \
  --evaluation-frequency 1h \
  --action-group <action-group-id>
```

---

## Cost Considerations

| Feature | Cost Impact |
|---------|-------------|
| Periodic Backup | Low (included in base cost) |
| Continuous Backup (7-day) | ~15-20% additional |
| Continuous Backup (30-day) | ~25-30% additional |
| Geo-replication | 2x storage + write costs |
| Zone redundancy | ~25% additional |

### Cost Optimization Tips

1. Use Periodic backup for dev/test environments
2. Enable Continuous backup only for production
3. Consider regional pair selection for geo-replication costs
4. Review backup retention requirements quarterly

---

## Related Documentation

- [Deployment Guide](./deployment.md) - Infrastructure deployment
- [Configuration Guide](./configuration.md) - Environment variables
- [Azure Cosmos DB Backup Documentation](https://learn.microsoft.com/en-us/azure/cosmos-db/online-backup-and-restore)
- [Azure Blob Storage Soft Delete](https://learn.microsoft.com/en-us/azure/storage/blobs/soft-delete-blob-overview)

---

*Last Updated: December 2024*
