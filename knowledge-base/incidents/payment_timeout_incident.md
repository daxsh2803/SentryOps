# Incident: Payment Gateway Timeout (INC-999)

## Metadata
* service: payment-service
* fault_type: http_500_spike
* timestamp: 2026-05-12T14:30:00Z
* source: historic-incidents

## Description
The payment-service experienced a sudden spike in HTTP 500 errors. 
This was accompanied by increased latency and connection timeouts to the upstream payment gateway.

## Symptoms
* Elevated 500 error rate
* Trace spans showing long latency in external API calls
* Order creation failing due to payment timeout

## Resolution
The issue was mitigated by horizontally scaling the payment service pods and failing over to the secondary payment gateway until the primary provider restored stability.
