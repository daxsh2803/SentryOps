import test from 'node:test';
import assert from 'node:assert/strict';
import { generateMarkdownReport, generateHtmlReport } from '../frontend/src/utils/reportGenerator.ts';

test('Report Generator - Complete Incident', () => {
  const completeData = {
    incident: {
      id: 25,
      incident_id: 'INC-CD90E2',
      title: 'Payment Service HTTP 500 Spike Incident',
      description: 'High rate of HTTP 500 errors detected on payment processing endpoint',
      status: 'RESOLVED',
      severity: 'HIGH',
      affected_service: 'payment-service',
      fault_type: 'http_500_spike',
      created_at: '2026-10-10T09:50:51.040063Z',
      updated_at: '2026-10-10T09:52:32.683951Z',
      started_at: null,
      resolved_at: '2026-10-10T09:52:32.683951Z'
    },
    timeline: [
      {
        event_type: 'INCIDENT_CREATED',
        source: 'incident-api',
        message: 'Incident detected via alerts',
        timestamp: '2026-10-10T09:50:51.040063Z'
      },
      {
        event_type: 'VERIFICATION_SUCCEEDED',
        source: 'verification-engine',
        message: 'All verification checks passed',
        timestamp: '2026-10-10T09:52:32.000000Z'
      }
    ],
    evidence: [
      {
        evidence_id: 'EV-TRACE-1234',
        evidence_type: 'TRACE',
        source: 'TraceAgent',
        service: 'payment-service',
        summary: '7 error spans found in payment traces',
        confidence: 0.95,
        payload: { trace_count: 10, error_spans: 7 },
        timestamp: '2026-10-10T09:51:00Z'
      }
    ],
    rca: {
      id: 1,
      root_cause: 'Mocked Root Cause: downstream payment-service failure rate',
      confidence: 0.9,
      evidence_ids: ['EV-TRACE-1234'],
      status: 'RESOLVED',
      identified_at: '2026-10-10T09:51:30Z'
    },
    remediation: {
      remediation: {
        id: 1,
        action_type: 'SCALE_SERVICE',
        description: '[DEMO FIXTURE - MOCK_LLM] Scale service replicas to 2',
        status: 'EXECUTED',
        parameters: { replicas: 2, target_service: 'payment-service' }
      },
      approval: {
        id: 1,
        status: 'APPROVED',
        reason: 'Live Demo Approval',
        resolved_at: '2026-10-10T09:52:00Z'
      },
      execution: {
        id: 1,
        status: 'SUCCESS',
        result: { scaled_replicas: 2 }
      }
    },
    risk: {
      risk_level: 'MEDIUM',
      reasons: ['Scaling production replicas requires verification'],
      risk_score: 55
    },
    verification: {
      id: 1,
      status: 'VERIFIED_SUCCESS',
      summary: 'Verification succeeded for SCALE_SERVICE on payment-service.',
      verified: true,
      checks: [
        { name: 'replica_count', expected: '2 replicas running', observed: '2 replicas running', passed: true },
        { name: 'service_health', expected: 'healthy', observed: 'healthy', passed: true }
      ]
    },
    evaluation: {
      evaluation_id: 'EVAL-001',
      overall_status: 'PASS',
      summary: 'Lifecycle completed with all stages verified.',
      investigation_result: 'PASS',
      rca_result: 'PASS',
      remediation_result: 'PASS',
      verification_result: 'PASS'
    },
    replay: {
      replay_id: 'REPLAY-001',
      replay_consistency: 'MATCH',
      summary: 'Replay matches historical record.'
    },
    postmortem: {
      postmortem_id: 'PM-001',
      title: 'Payment 500 Outage Postmortem',
      summary: 'Downstream payment failure mitigated by scaling.',
      impact: '0 orders dropped during active period.',
      lessons: ['Enhance automated retry backoff.']
    }
  };

  const md = generateMarkdownReport(completeData);

  // Assertions for complete report
  assert.ok(md.includes('# SentryOps Incident Report: INC-CD90E2'));
  assert.ok(md.includes('Payment Service HTTP 500 Spike Incident'));
  assert.ok(md.includes('payment-service'));
  assert.ok(md.includes('http_500_spike'));
  assert.ok(md.includes('RESOLVED'));
  assert.ok(md.includes('EV-TRACE-1234'));
  assert.ok(md.includes('SCALE_SERVICE'));
  assert.ok(md.includes('VERIFIED_SUCCESS'));
  assert.ok(md.includes('Live Demo Approval'));
  assert.ok(md.includes('EVAL-001'));
  assert.ok(md.includes('MATCH'));
  assert.ok(md.includes('PM-001'));

  // Disclosure labels
  assert.ok(md.includes('[DEMO FIXTURE - MOCK_LLM'));
  assert.ok(md.includes('SIMULATED_INFRA_STATE'));

  // HTML Generation
  const html = generateHtmlReport(completeData);
  assert.ok(html.includes('<!DOCTYPE html>'));
  assert.ok(html.includes('INC-CD90E2'));
  assert.ok(html.includes('Payment Service HTTP 500 Spike Incident'));
  assert.ok(html.includes('SCALE_SERVICE'));
  assert.ok(html.includes('<table>'));
});

test('Report Generator - Pending / Incomplete Incident', () => {
  const pendingData = {
    incident: {
      id: 26,
      incident_id: 'INC-8A4949',
      title: 'Active Fault Incident',
      description: 'Controlled fault in progress',
      status: 'INVESTIGATING',
      severity: 'HIGH',
      affected_service: 'payment-service',
      fault_type: 'http_500_spike',
      created_at: '2026-10-15T13:41:54Z',
      updated_at: '2026-10-15T13:43:10Z'
    },
    timeline: [
      {
        event_type: 'INCIDENT_CREATED',
        source: 'incident-api',
        message: 'Incident detected',
        timestamp: '2026-10-15T13:41:54Z'
      }
    ],
    evidence: [],
    rca: null,
    remediation: null,
    risk: null,
    verification: null,
    evaluation: null,
    replay: null,
    postmortem: null
  };

  const md = generateMarkdownReport(pendingData);

  // Assertions for incomplete stages
  assert.ok(md.includes('INC-8A4949'));
  assert.ok(md.includes('INVESTIGATING'));
  assert.ok(md.includes('Pending Resolution / Ongoing'));
  assert.ok(md.includes('No evidence collected yet (Investigation pending or not initiated)'));
  assert.ok(md.includes('STAGE PENDING: RCA has not been generated for this incident'));
  assert.ok(md.includes('STAGE PENDING: No remediation action proposed yet'));
  assert.ok(md.includes('STAGE PENDING / NOT COMPLETED: Remediation verification has not taken place'));
  assert.ok(md.includes('STAGE PENDING: Evaluation framework has not been evaluated'));
  assert.ok(md.includes('STAGE PENDING: Postmortem document has not been generated'));

  // Ensure no fabricated verification success
  assert.ok(!md.includes('VERIFIED_SUCCESS'));
  assert.ok(!md.includes('Execution SUCCESS'));
});
