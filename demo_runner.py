import requests
import time
import json
import os
import matplotlib.pyplot as plt

BASE_DIR = os.path.join(os.path.dirname(__file__), "docs", "images", "demo")
os.makedirs(BASE_DIR, exist_ok=True)

BACKEND_URL = "http://127.0.0.1:8000"
API_GATEWAY_URL = "http://127.0.0.1:8080"
FAULT_URL = "http://127.0.0.1:8005"
PROM_URL = "http://127.0.0.1:9090"

def generate_workload(count=15, delay=0.1):
    success = 0
    failed = 0
    latencies = []
    for _ in range(count):
        start = time.time()
        try:
            r = requests.post(f"{API_GATEWAY_URL}/orders", json={"amount": 100}, timeout=3)
            if r.status_code == 200:
                success += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
        latencies.append(time.time() - start)
        time.sleep(delay)
    return {"success": success, "failed": failed, "avg_latency": sum(latencies)/len(latencies) if latencies else 0}

def get_prom_metric(query):
    try:
        r = requests.get(f"{PROM_URL}/api/v1/query", params={"query": query})
        data = r.json()
        if data['status'] == 'success' and data['data']['result']:
            return float(data['data']['result'][0]['value'][1])
    except:
        pass
    return 0.0

def main():
    print("1. Collecting baseline workload...")
    base_stats = generate_workload(15)
    print("Baseline:", base_stats)

    print("2. Injecting fault...")
    fault_payload = {
        "fault_type": "http_500_spike",
        "target_service": "payment-service",
        "parameters": {"error_rate": 0.8}
    }
    r = requests.post(f"{FAULT_URL}/faults/inject", json=fault_payload)
    fault_id = r.json().get("fault_id")
    print("Fault injected:", fault_id)

    print("3. Generating incident workload...")
    incident_stats = generate_workload(15)
    print("Incident stats:", incident_stats)

    print("4. Creating incident in backend...")
    inc_payload = {
        "title": "Payment Service 500 Spike",
        "description": "Automated demo detection",
        "severity": "HIGH",
        "affected_service": "payment-service",
        "fault_type": "http_500_spike"
    }
    r = requests.post(f"{BACKEND_URL}/incidents", json=inc_payload)
    inc_data = r.json()
    incident_id = inc_data["incident_id"]
    print("Incident created:", incident_id)

    print("5. Triggering AI Investigation...")
    r = requests.post(f"{BACKEND_URL}/incidents/{incident_id}/ai-investigate")
    print("AI Investigation started.")

    time.sleep(5)

    # Check remediation
    rem_data = requests.get(f"{BACKEND_URL}/incidents/{incident_id}/remediation").json()
    print("Remediation Proposal:", rem_data)

    print("6. Approving Remediation...")
    requests.post(f"{BACKEND_URL}/incidents/{incident_id}/approve", json={"reason": "Live Demo Approval"})

    time.sleep(2)
    print("7. Generating post-remediation workload...")
    # Clean up fault to actually simulate recovery
    requests.post(f"{FAULT_URL}/faults/{fault_id}/cleanup")
    time.sleep(2)
    post_stats = generate_workload(15)
    print("Post-remediation stats:", post_stats)

    # Save chart
    stages = ['Baseline', 'Incident', 'Post-Remediation']
    successes = [base_stats['success'], incident_stats['success'], post_stats['success']]
    failures = [base_stats['failed'], incident_stats['failed'], post_stats['failed']]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(stages, successes, label='Success (200 OK)', color='#2ca02c')
    ax.bar(stages, failures, bottom=successes, label='Failures (5xx)', color='#d62728')
    ax.set_ylabel('Number of Requests')
    ax.set_title('Payment Service HTTP 500 Spike Scenario')
    ax.legend()
    plt.savefig(os.path.join(BASE_DIR, "service_health.png"))
    print("Saved chart to docs/images/demo/service_health.png")

    with open(os.path.join(BASE_DIR, "demo_results.json"), "w") as f:
        json.dump({
            "incident_id": incident_id,
            "baseline": base_stats,
            "incident": incident_stats,
            "post_remediation": post_stats,
            "remediation_proposal": rem_data
        }, f, indent=2)

if __name__ == "__main__":
    main()
