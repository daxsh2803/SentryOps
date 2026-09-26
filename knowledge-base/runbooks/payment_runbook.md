# Runbook: Payment Service Troubleshooting

## Metadata
* service: payment-service
* fault_type: database_crash
* source: devops-wiki

## Diagnostic Steps
1. Check if the PostgreSQL database is reachable from the payment-service.
2. Verify connection pool metrics. 
3. Check the payment-service logs for "connection refused" or "database timeout".

## Remediation
* If the database is unresponsive, verify the primary DB instance health.
* Restart the payment-service to flush stalled connection pools.
* Scale down non-critical consumers if DB load is too high.
