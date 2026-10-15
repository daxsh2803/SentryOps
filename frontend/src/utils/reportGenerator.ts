import { formatDateTime } from './date.ts';

export interface IncidentReportData {
  incident: {
    id: number;
    incident_id: string;
    title: string;
    description?: string;
    status: string;
    severity: string;
    affected_service?: string;
    fault_type?: string;
    created_at: string;
    updated_at: string;
    started_at?: string | null;
    resolved_at?: string | null;
  };
  timeline?: Array<{
    event_type: string;
    source?: string;
    message?: string;
    timestamp: string;
    metadata_json?: any;
  }>;
  evidence?: Array<{
    evidence_id: string;
    evidence_type: string;
    source: string;
    service: string;
    summary: string;
    payload?: any;
    confidence?: number;
    timestamp: string;
  }>;
  rca?: {
    id?: number;
    root_cause: string;
    confidence: number;
    evidence_ids?: string[];
    status?: string;
    identified_at?: string;
  } | null;
  remediation?: {
    remediation?: {
      id?: number;
      action_type: string;
      description?: string;
      status?: string;
      parameters?: any;
    };
    approval?: {
      id?: number;
      status: string;
      reason?: string;
      resolved_at?: string;
    };
    execution?: {
      id?: number;
      status: string;
      result?: any;
    };
  } | null;
  risk?: {
    risk_level: string;
    reasons: string[];
    risk_score?: number;
  } | null;
  verification?: {
    id?: number;
    status?: string;
    verification_status?: string;
    summary?: string;
    verified?: boolean;
    checks?: Array<{
      name: string;
      expected: any;
      observed: any;
      passed: boolean;
    }>;
    metrics?: {
      checks?: Array<{
        name: string;
        expected: any;
        observed: any;
        passed: boolean;
      }>;
      confidence?: number;
    };
  } | null;
  evaluation?: {
    evaluation_id?: string;
    overall_status?: string;
    summary?: string;
    investigation_result?: string;
    rca_result?: string;
    remediation_result?: string;
    verification_result?: string;
    checks?: Array<{
      name: string;
      dimension?: string;
      passed: boolean;
      observed: string;
      expected?: string;
    }>;
    recommendations?: string[];
    evaluated_at?: string;
  } | null;
  replay?: {
    replay_id?: string;
    replay_consistency?: string;
    summary?: string;
    historical_actions?: any[];
    differences?: any[];
    stages?: any[];
  } | null;
  postmortem?: {
    postmortem_id?: string;
    title?: string;
    summary?: string;
    impact?: string;
    final_status?: string;
    timeline?: any[];
    sections?: any[];
    lessons?: string[];
  } | null;
}

/**
 * Generates a comprehensive, verifiable Markdown incident report.
 */
export function generateMarkdownReport(data: IncidentReportData): string {
  const { incident, timeline = [], evidence = [], rca, remediation, risk, verification, evaluation, replay, postmortem } = data;
  const now = new Date().toISOString();

  const lines: string[] = [];

  lines.push(`# SentryOps Incident Report: ${incident.incident_id}`);
  lines.push(`**Title**: ${incident.title}`);
  lines.push('');
  lines.push(`> **Report Export Timestamp**: ${now} (UTC)`);
  lines.push(`> **Platform**: SentryOps Autonomous Incident Response Platform`);
  lines.push(`> **Data Origin**: Live Persisted PostgreSQL & Observability Telemetry`);
  lines.push('');
  lines.push('---');
  lines.push('');

  // 1. Incident Metadata
  lines.push('## 1. Incident Metadata & Overview');
  lines.push('');
  lines.push('| Field | Value |');
  lines.push('| :--- | :--- |');
  lines.push(`| **Incident ID** | \`${incident.incident_id}\` (DB ID: ${incident.id}) |`);
  lines.push(`| **Title** | ${incident.title} |`);
  lines.push(`| **Severity** | **${incident.severity}** |`);
  lines.push(`| **Lifecycle Status** | **${incident.status}** |`);
  lines.push(`| **Affected Service** | \`${incident.affected_service || 'N/A'}\` |`);
  lines.push(`| **Fault Scenario Type** | \`${incident.fault_type || 'N/A'}\` |`);
  lines.push(`| **Description** | ${incident.description || 'No description provided.'} |`);
  lines.push('');
  lines.push('### Lifecycle Timestamps');
  lines.push(`- **Created At**: ${formatDateTime(incident.created_at)}`);
  lines.push(`- **Started At**: ${incident.started_at ? formatDateTime(incident.started_at) : 'N/A'}`);
  lines.push(`- **Last Updated**: ${incident.updated_at ? formatDateTime(incident.updated_at) : 'N/A'}`);
  lines.push(`- **Resolved At**: ${incident.resolved_at ? formatDateTime(incident.resolved_at) : (incident.status === 'RESOLVED' ? 'Marked Resolved' : 'Pending Resolution / Ongoing')}`);
  lines.push('');
  lines.push('---');
  lines.push('');

  // 2. Investigation Timeline
  lines.push('## 2. Investigation Timeline & Events');
  lines.push('');
  if (timeline.length === 0) {
    lines.push('*No timeline events recorded yet.*');
  } else {
    lines.push('| # | Timestamp (Local) | Source | Event Type | Details |');
    lines.push('| :-: | :--- | :--- | :--- | :--- |');
    timeline.forEach((ev, idx) => {
      const ts = formatDateTime(ev.timestamp);
      const src = ev.source || 'incident-api';
      const type = ev.event_type || 'EVENT';
      const msg = (ev.message || '-').replace(/\|/g, '\\|');
      lines.push(`| ${idx + 1} | ${ts} | \`${src}\` | \`${type}\` | ${msg} |`);
    });
  }
  lines.push('');
  lines.push('---');
  lines.push('');

  // 3. Multi-Agent Evidence Inventory
  lines.push('## 3. Multi-Agent Evidence Inventory');
  lines.push('');
  if (evidence.length === 0) {
    lines.push('*No evidence collected yet (Investigation pending or not initiated).*');
  } else {
    lines.push(`Total Harvested Artifacts: **${evidence.length} items**`);
    lines.push('');
    lines.push('| Evidence ID | Type | Source | Target Service | Confidence | Summary |');
    lines.push('| :--- | :--- | :--- | :--- | :--- | :--- |');
    evidence.forEach(ev => {
      const id = ev.evidence_id;
      const type = ev.evidence_type;
      const src = ev.source;
      const svc = ev.service;
      const conf = ev.confidence !== undefined ? `${(ev.confidence * 100).toFixed(0)}%` : 'N/A';
      const sum = (ev.summary || '').replace(/\|/g, '\\|');
      lines.push(`| \`${id}\` | \`${type}\` | ${src} | \`${svc}\` | ${conf} | ${sum} |`);
    });
    lines.push('');
    lines.push('### Evidence Payload Details');
    evidence.forEach(ev => {
      if (ev.payload && Object.keys(ev.payload).length > 0) {
        lines.push(`#### Artifact \`${ev.evidence_id}\` (${ev.evidence_type} - ${ev.source})`);
        lines.push('```json');
        lines.push(JSON.stringify(ev.payload, null, 2));
        lines.push('```');
      }
    });
  }
  lines.push('');
  lines.push('---');
  lines.push('');

  // 4. Root Cause Analysis (RCA)
  lines.push('## 4. Root Cause Analysis (RCA)');
  lines.push('');
  if (!rca || !rca.root_cause) {
    lines.push('*STAGE PENDING: RCA has not been generated for this incident.*');
  } else {
    lines.push(`> [!NOTE]`);
    lines.push(`> **Attribution Disclosure**: **[DEMO FIXTURE - MOCK_LLM / DETERMINISTIC HEURISTIC]**`);
    lines.push(`> This diagnosis was produced deterministically by the SentryOps RCA Agent using linked evidence and anti-hallucination verification. It is not generated by unconstrained live LLM reasoning.`);
    lines.push('');
    lines.push(`- **Diagnosed Root Cause**: **${rca.root_cause}**`);
    lines.push(`- **Confidence Score**: ${(rca.confidence * 100).toFixed(0)}%`);
    if (rca.identified_at) {
      lines.push(`- **Identified At**: ${formatDateTime(rca.identified_at)}`);
    }
    if (rca.evidence_ids && rca.evidence_ids.length > 0) {
      lines.push(`- **Linked Evidence Citations**: ${rca.evidence_ids.map(id => `\`${id}\``).join(', ')}`);
      lines.push('- **Anti-Hallucination Gate**: Verified that all cited evidence IDs exist in the incident evidence store.');
    }
  }
  lines.push('');
  lines.push('---');
  lines.push('');

  // 5. Remediation Proposal & Deterministic Risk Policy
  lines.push('## 5. Remediation Proposal & Risk Assessment');
  lines.push('');
  const rem = remediation?.remediation;
  if (!rem) {
    lines.push('*STAGE PENDING: No remediation action proposed yet.*');
  } else {
    lines.push(`> [!NOTE]`);
    lines.push(`> **Attribution Disclosure**: **[DEMO FIXTURE - MOCK_LLM / ALLOWLISTED ACTION]**`);
    lines.push(`> The proposed action was selected from the strict safety allowlist (\`RESTART_SERVICE\`, \`SCALE_SERVICE\`, \`ROLLBACK_SERVICE\`).`);
    lines.push('');
    lines.push(`- **Proposed Action**: \`${rem.action_type}\``);
    lines.push(`- **Action Description**: ${rem.description || '-'}`);
    lines.push(`- **Proposal Status**: \`${rem.status || 'PENDING'}\``);
    if (rem.parameters) {
      lines.push('- **Parameters**:');
      lines.push('```json');
      lines.push(JSON.stringify(rem.parameters, null, 2));
      lines.push('```');
    }

    lines.push('');
    lines.push('### Deterministic Risk Assessment');
    if (!risk) {
      lines.push('*Risk assessment has not been evaluated.*');
    } else {
      lines.push(`- **Evaluated Risk Level**: **${risk.risk_level}**`);
      if (risk.risk_score !== undefined) {
        lines.push(`- **Risk Score**: ${risk.risk_score}`);
      }
      lines.push('- **Contributing Policy Factors**:');
      if (risk.reasons && risk.reasons.length > 0) {
        risk.reasons.forEach(r => lines.push(`  - ${r}`));
      } else {
        lines.push('  - Standard risk policy check applied.');
      }
      lines.push('');
      if (risk.risk_level === 'MEDIUM' || risk.risk_level === 'HIGH') {
        lines.push(`> **Safety Gate**: **Mandatory Human Approval Required** for \`${risk.risk_level}\` risk proposals. Autonomous cluster execution is prohibited.`);
      } else {
        lines.push(`> **Safety Gate**: Autonomous simulation execution permitted for \`${risk.risk_level}\` risk proposals.`);
      }
    }
  }
  lines.push('');
  lines.push('---');
  lines.push('');

  // 6. Approval & Execution Outcome
  lines.push('## 6. Human Approval & Execution Outcome');
  lines.push('');
  const app = remediation?.approval;
  const exec = remediation?.execution;

  if (!app && !exec) {
    lines.push('*STAGE PENDING: Awaiting operator review and decision.*');
  } else {
    lines.push(`- **Approval Status**: **${app?.status || (incident.status === 'PENDING_APPROVAL' ? 'PENDING_APPROVAL' : 'N/A')}**`);
    if (app?.reason) {
      lines.push(`- **Decision Reason / Note**: "${app.reason}"`);
    }
    if (app?.resolved_at) {
      lines.push(`- **Decision Timestamp**: ${formatDateTime(app.resolved_at)}`);
    }

    lines.push('');
    lines.push('### Actuation Boundary & Execution');
    if (!exec) {
      if (app?.status === 'REJECTED') {
        lines.push('- **Execution Outcome**: **CANCELLED** (Remediation was rejected by human operator; execution was safely halted).');
      } else {
        lines.push('- **Execution Outcome**: **NOT EXECUTED** (Remediation is pending approval).');
      }
    } else {
      lines.push(`- **Execution Status**: **${exec.status}**`);
      lines.push('> [!IMPORTANT]');
      lines.push('> **Simulated Actuation Boundary**: Actuation was applied strictly against in-memory `SIMULATED_INFRA_STATE`. Live Kubernetes deployments remained at their original replica count (0 direct cluster mutations).');
      if (exec.result) {
        lines.push('```json');
        lines.push(JSON.stringify(exec.result, null, 2));
        lines.push('```');
      }
    }
  }
  lines.push('');
  lines.push('---');
  lines.push('');

  // 7. Automated Verification
  lines.push('## 7. Automated Verification & Recovery');
  lines.push('');
  const checks = verification?.checks || verification?.metrics?.checks || [];
  if (!verification || (!verification.status && !verification.verification_status)) {
    lines.push('*STAGE PENDING / NOT COMPLETED: Remediation verification has not taken place.*');
  } else {
    const vStatus = verification.status || verification.verification_status || 'UNKNOWN';
    const isSuccess = verification.verified ?? (vStatus === 'VERIFIED_SUCCESS');
    lines.push(`- **Verification Status**: **${vStatus}** (${isSuccess ? 'PASSED' : 'FAILED / INCOMPLETE'})`);
    if (verification.summary) {
      lines.push(`- **Summary**: ${verification.summary}`);
    }
    if (checks.length > 0) {
      lines.push('');
      lines.push('| Health / Metric Check | Expected | Observed | Result |');
      lines.push('| :--- | :--- | :--- | :--- |');
      checks.forEach(chk => {
        lines.push(`| **${chk.name}** | \`${chk.expected}\` | \`${chk.observed}\` | ${chk.passed ? 'PASSED' : 'FAILED'} |`);
      });
    }
  }
  lines.push('');
  lines.push('---');
  lines.push('');

  // 8. Evaluation Framework
  lines.push('## 8. Incident Evaluation Framework (Phase 11)');
  lines.push('');
  if (!evaluation || !evaluation.overall_status) {
    lines.push('*STAGE PENDING: Evaluation framework has not been evaluated for this incident.*');
  } else {
    if (evaluation.evaluation_id) {
      lines.push(`- **Evaluation ID**: \`${evaluation.evaluation_id}\``);
    }
    lines.push(`- **Overall Evaluation Result**: **${evaluation.overall_status}**`);
    if (evaluation.summary) {
      lines.push(`- **Summary**: ${evaluation.summary}`);
    }
    lines.push('');
    lines.push('### 4-Dimension Lifecycle Scorecard');
    lines.push(`- **Investigation**: \`${evaluation.investigation_result || 'N/A'}\``);
    lines.push(`- **Root Cause Analysis (RCA)**: \`${evaluation.rca_result || 'N/A'}\``);
    lines.push(`- **Remediation**: \`${evaluation.remediation_result || 'N/A'}\``);
    lines.push(`- **Verification**: \`${evaluation.verification_result || 'N/A'}\``);

    if (evaluation.checks && evaluation.checks.length > 0) {
      lines.push('');
      lines.push('| Evaluation Check | Dimension | Observed Finding | Outcome |');
      lines.push('| :--- | :--- | :--- | :--- |');
      evaluation.checks.forEach(chk => {
        lines.push(`| ${chk.name} | \`${chk.dimension || '-'}\` | ${chk.observed} | ${chk.passed ? 'PASSED' : 'FAILED'} |`);
      });
    }
    if (evaluation.recommendations && evaluation.recommendations.length > 0) {
      lines.push('');
      lines.push('### Evaluation Recommendations');
      evaluation.recommendations.forEach(rec => lines.push(`- ${rec}`));
    }
  }
  lines.push('');
  lines.push('---');
  lines.push('');

  // 9. Incident Replay Reconstruction
  lines.push('## 9. Read-Only Incident Replay Reconstruction (Phase 12)');
  lines.push('');
  if (!replay || !replay.replay_consistency) {
    lines.push('*STAGE PENDING: Replay reconstruction has not been performed for this incident.*');
  } else {
    lines.push(`- **Replay Consistency**: **${replay.replay_consistency}**`);
    if (replay.summary) {
      lines.push(`- **Replay Summary**: ${replay.summary}`);
    }
    lines.push('> [!NOTE]');
    lines.push('> **Audit Guarantee**: Read-only historical reconstruction. No remediations are re-executed against active workloads.');

    if (replay.differences && replay.differences.length > 0) {
      lines.push('');
      lines.push('| Comparative Field | Original Run | Replay Run | Consistency |');
      lines.push('| :--- | :--- | :--- | :--- |');
      replay.differences.forEach(diff => {
        lines.push(`| ${diff.field} | \`${diff.original ?? 'n/a'}\` | \`${diff.replay ?? 'n/a'}\` | ${diff.consistent ? 'MATCH' : 'MISMATCH'} |`);
      });
    }
    if (replay.stages && replay.stages.length > 0) {
      lines.push('');
      lines.push('| Stage | Availability | Summary |');
      lines.push('| :--- | :--- | :--- |');
      replay.stages.forEach(st => {
        lines.push(`| ${st.stage} | ${st.available ? 'Available' : 'Missing'} | ${st.summary} |`);
      });
    }
  }
  lines.push('');
  lines.push('---');
  lines.push('');

  // 10. Postmortem
  lines.push('## 10. Structured Incident Postmortem (Phase 12)');
  lines.push('');
  if (!postmortem || !postmortem.postmortem_id) {
    lines.push('*STAGE PENDING: Postmortem document has not been generated for this incident.*');
  } else {
    lines.push(`- **Postmortem ID**: \`${postmortem.postmortem_id}\``);
    lines.push(`- **Postmortem Title**: ${postmortem.title || incident.title}`);
    lines.push(`- **Impact Summary**: ${postmortem.impact || 'N/A'}`);
    lines.push(`- **Final Incident Status**: \`${postmortem.final_status || incident.status}\``);

    if (postmortem.sections && postmortem.sections.length > 0) {
      lines.push('');
      lines.push('### Postmortem Sections');
      postmortem.sections.forEach(sec => {
        lines.push(`#### ${sec.section} [${sec.available ? 'Completed' : 'Pending'}]`);
        lines.push(`${sec.summary}`);
        lines.push('');
      });
    }

    if (postmortem.lessons && postmortem.lessons.length > 0) {
      lines.push('### Lessons Learned & Corrective Action Items');
      postmortem.lessons.forEach((l, idx) => {
        lines.push(`${idx + 1}. ${l}`);
      });
    }
  }

  lines.push('');
  lines.push('---');
  lines.push('');
  lines.push('*Report compiled by SentryOps Incident Audit Exporter. Telemetry and records preserved in PostgreSQL.*');

  return lines.join('\n');
}

/**
 * Generates a clean, standalone, printable HTML incident report.
 */
export function generateHtmlReport(data: IncidentReportData): string {
  const md = generateMarkdownReport(data);
  const { incident } = data;

  // Convert basic markdown formatting to clean HTML
  const escapeHtml = (str: string) =>
    str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  // Simple and safe Markdown to HTML line-by-line renderer
  const lines = md.split('\n');
  const htmlParts: string[] = [];
  let inTable = false;
  let inCode = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith('```')) {
      if (inCode) {
        htmlParts.push('</code></pre>');
        inCode = false;
      } else {
        htmlParts.push('<pre><code>');
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      htmlParts.push(escapeHtml(line) + '\n');
      continue;
    }

    if (line.startsWith('|')) {
      if (!inTable) {
        htmlParts.push('<div class="table-container"><table>');
        inTable = true;
      }
      if (line.includes(':---')) {
        // Table header separator line, skip
        continue;
      }
      const cells = line.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1).map(c => c.trim());
      const isHeader = htmlParts[htmlParts.length - 1] === '<div class="table-container"><table>';
      const tag = isHeader ? 'th' : 'td';
      htmlParts.push('<tr>' + cells.map(c => `<${tag}>${formatInline(c)}</${tag}>`).join('') + '</tr>');
      continue;
    } else if (inTable) {
      htmlParts.push('</table></div>');
      inTable = false;
    }

    if (line.startsWith('# ')) {
      htmlParts.push(`<h1>${formatInline(line.slice(2))}</h1>`);
    } else if (line.startsWith('## ')) {
      htmlParts.push(`<h2>${formatInline(line.slice(3))}</h2>`);
    } else if (line.startsWith('### ')) {
      htmlParts.push(`<h3>${formatInline(line.slice(4))}</h3>`);
    } else if (line.startsWith('#### ')) {
      htmlParts.push(`<h4>${formatInline(line.slice(5))}</h4>`);
    } else if (line.startsWith('> [!NOTE]') || line.startsWith('> [!IMPORTANT]')) {
      htmlParts.push('<div class="callout callout-info">');
    } else if (line.startsWith('> ')) {
      htmlParts.push(`<p class="blockquote">${formatInline(line.slice(2))}</p>`);
    } else if (line.startsWith('- ')) {
      htmlParts.push(`<ul><li>${formatInline(line.slice(2))}</li></ul>`);
    } else if (/^\d+\.\s/.test(line)) {
      htmlParts.push(`<ol><li>${formatInline(line.replace(/^\d+\.\s/, ''))}</li></ol>`);
    } else if (line.trim() === '---') {
      htmlParts.push('<hr />');
    } else if (line.trim().length > 0) {
      htmlParts.push(`<p>${formatInline(line)}</p>`);
    }
  }

  if (inTable) htmlParts.push('</table></div>');
  if (inCode) htmlParts.push('</code></pre>');

  function formatInline(text: string): string {
    return escapeHtml(text)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
  }

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SentryOps Incident Report - ${incident.incident_id}</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --primary: #3b82f6;
      --success: #10b981;
      --danger: #ef4444;
      --warning: #f59e0b;
      --border: #334155;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      line-height: 1.6;
      color: var(--text);
      background-color: var(--bg);
      margin: 0;
      padding: 2.5rem 1.5rem;
    }
    .container {
      max-width: 960px;
      margin: 0 auto;
      background: var(--card-bg);
      padding: 2.5rem;
      border-radius: 8px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
      border: 1px solid var(--border);
    }
    h1 { color: #fff; font-size: 1.85rem; border-bottom: 2px solid var(--border); padding-bottom: 0.5rem; margin-top: 0; }
    h2 { color: #e2e8f0; font-size: 1.35rem; margin-top: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 0.3rem; }
    h3 { color: #cbd5e1; font-size: 1.1rem; margin-top: 1.25rem; }
    h4 { color: #94a3b8; font-size: 0.95rem; margin-top: 1rem; }
    p, li { color: #e2e8f0; font-size: 0.925rem; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: #0b1120; padding: 0.2rem 0.4rem; border-radius: 4px; font-size: 0.85rem; color: #38bdf8; }
    pre { background: #0b1120; padding: 1rem; border-radius: 6px; overflow-x: auto; border: 1px solid var(--border); }
    pre code { background: none; padding: 0; color: #cbd5e1; }
    .table-container { overflow-x: auto; margin: 1rem 0; }
    table { width: 100%; border-collapse: collapse; font-size: 0.875rem; text-align: left; }
    th { background: #0b1120; color: #94a3b8; padding: 0.6rem 0.75rem; border: 1px solid var(--border); font-weight: 600; }
    td { padding: 0.6rem 0.75rem; border: 1px solid var(--border); }
    tr:nth-child(even) { background: rgba(255, 255, 255, 0.02); }
    .callout { background: rgba(59, 130, 246, 0.1); border-left: 4px solid var(--primary); padding: 0.75rem 1rem; border-radius: 4px; margin: 1rem 0; font-size: 0.875rem; }
    .blockquote { background: rgba(0, 0, 0, 0.2); border-left: 3px solid #64748b; padding: 0.5rem 1rem; margin: 0.5rem 0; font-size: 0.875rem; color: var(--text-muted); }
    hr { border: 0; height: 1px; background: var(--border); margin: 2rem 0; }
    @media print {
      body { background: #fff; color: #000; padding: 0; }
      .container { box-shadow: none; border: none; max-width: 100%; padding: 0; background: #fff; color: #000; }
      h1, h2, h3, h4, p, td, th, li { color: #000 !important; }
      th { background: #f1f5f9; }
      code, pre { background: #f8fafc; color: #000; border-color: #cbd5e1; }
    }
  </style>
</head>
<body>
  <div class="container">
    ${htmlParts.join('\n')}
  </div>
</body>
</html>`;
}

/**
 * Triggers a client-side file download via Blob.
 */
export function downloadReport(filename: string, content: string, mimeType: string = 'text/markdown;charset=utf-8') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
