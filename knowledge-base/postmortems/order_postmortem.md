# Postmortem: Order Service Outage

## Metadata
* service: order-service
* fault_type: cpu_stress
* source: postmortems

## Summary
The order-service went down due to CPU exhaustion when processing a large batch of backlogged orders. 

## Root Cause
An inefficient nested loop in the order calculation logic caused the CPU to spike to 100%, leading to container OOM kills and unresponsiveness. 
Traces showed extreme latency in the `calculate_totals` function.

## Action Items
1. Optimize the `calculate_totals` loop.
2. Add CPU usage alerts for the order-service.
3. Implement a circuit breaker to prevent cascading failures to the inventory service.
