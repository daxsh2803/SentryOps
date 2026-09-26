# SentryOps

Autonomous Multi-Agent Production Incident Response and Root Cause Analysis Platform.

## Current Phase: Phase 0 (Foundation)
This phase establishes the foundational structure for the project.

### Architecture Guidelines
- **Microservices**: To be implemented in later phases.
- **Observability**: To be added in later phases.
- **Agents/LangGraph**: To be added in later phases.
- **Fault Injection**: To be added in later phases.
- **Evaluation**: To be added in later phases.
- **Infrastructure**: To be expanded in later phases.

## Technology Stack (Target)
- **Backend**: Python, FastAPI, LangGraph, Pydantic
- **Frontend**: React, TypeScript
- **Database**: PostgreSQL with pgvector, Redis
- **Observability**: OpenTelemetry, Prometheus, Grafana, Jaeger, Loki
- **Infrastructure**: Docker, Docker Compose


## Phase 3 (Fault Injection)
This phase introduces a Fault Injection framework, independent from future AI phases, which produces deterministic incident failures within the simulated environment. 

### Fault Injection Architecture
- **Fault Manager**: Exposed via the ault-injection microservice API on port 8005.
- **Fault Lifecycle**: INACTIVE -> INJECTING -> ACTIVE -> STOPPING -> INACTIVE.
- **Scenarios**:
  - payment_service_crash: Returns HTTP 503 from the payment service.
  - http_500_spike: Injects HTTP 500 errors based on a configurable error_rate parameter.
  - rtificial_latency: Introduces sleep logic based on a delay_ms parameter.
  - db_connection_exhaustion: Simulates exhaustion of the database pool connection with a timeout.
  - ad_configuration: Simulates downstream configuration failures returning HTTP 502.

### Safety Constraints
Faults do not corrupt actual infrastructure (PostgreSQL/Redis are untouched) and exist purely as simulated runtime states pushed out via Redis. All fault payloads require a whitelisted ault_type from the scenario registry.

### How to use the Injection API
- GET /faults: List active faults.
- GET /faults/types: List available scenario types.
- POST /faults/inject: Start a fault.
  - Payload: {"fault_type": "artificial_latency", "target_service": "payment-service", "parameters": {"delay_ms": 3000}}
- POST /faults/{fault_id}/stop: Gracefully stops the fault.
- POST /faults/{fault_id}/cleanup: Unregisters the fault from memory.

### Ground Truth Metadata
Each created fault includes strongly-typed ground_truth_root_cause metadata. This provides deterministic answers for future AI RCAs to evaluate against.

### Manual Validation
1. Start stack: docker-compose up -d --build
2. Ensure health: Check http://localhost:8000/health
3. Send normal traffic: POST http://localhost:8000/orders with {"amount": 100}
4. Inject fault: POST http://localhost:8005/faults/inject with rtificial_latency.
5. Observe metrics in Prometheus and traces in Jaeger for the increased latency.
6. Stop fault: POST http://localhost:8005/faults/{fault_id}/cleanup.

**Note**: Phase 4 AI Agents, RAG, and Incident backend workflows remain intentionally deferred.

## Phase 4 (Incident Management Backend)
This phase introduces the core database and FastAPI foundation for the Incident Management Lifecycle. It establishes data persistence meant to be orchestrated by LangGraph in Phase 5.

### Features
- **PostgreSQL Persistence**: Schema includes Incident, IncidentEvent, Evidence, AgentExecution, RootCause, Remediation, Approval, Execution, and Verification tables (managed with SQLAlchemy).
- **Incident Creation API**: Manually tracks incident statuses, faults, and severities through endpoints like POST /incidents and GET /incidents/{id}.
- **Incident Timeline**: A chronological history of events like INCIDENT_CREATED and INVESTIGATION_STARTED.
- **Evidence Storage**: API structure allowing metrics, traces, and logs to be formally attached to incidents for later RCA evaluation.
- **Investigation Lifecycle**: Basic state machines enforcing DETECTED -> INVESTIGATING -> MITIGATING workflows.

### Note on Phase 4 Limitations
- Phase 4 is **data-only**. AI, RCA, automated remediations, and LangGraph pipelines have explicitly NOT been introduced yet.
- Vector retrieval, Embeddings, and pgvector are deferred.

## Phase 5 (Initial AI Agent Orchestration)
This phase introduces the first working AI investigation pipeline using LangGraph orchestration for Incident Manager, Log Agent, Metrics Agent, and RCA Agent. The pipeline must integrate with the existing Phase 1-4 infrastructure.

### Features
- **LangGraph Orchestration**: Introduced a graph connecting an IncidentManager node to parallel LogAgent and MetricsAgent nodes, terminating at an RCAAgent node.
- **Agent Integration**: 
  - LogAgent querying the existing loki endpoint.
  - MetricsAgent querying the existing prometheus endpoint.
  - RCAAgent utilizing langchain-core with mock models to deterministically synthesize evidence.
- **Investigation Endpoint**: Exposes POST /incidents/{incident_id}/ai-investigate which starts the orchestration workflow and saves execution footprints (Timeline, Evidence, RCA).

### Limitations
- The LLM integration defaults to a deterministic MockChatModel to guarantee CI consistency and allow testing without an LLM key.
- Remediations, Risk Engines, and pgvector integrations are intentionally deferred. 

## Phase 6 (Advanced Investigation)
This phase extends the AI agent orchestration pipeline with parallel deep investigation nodes:
- **TraceAgent**: Queries Jaeger distributed traces, parses span hierarchies, flags error tags/HTTP status codes, and records structured trace findings and evidence.
- **DeploymentAgent**: Examines environment change context and synthetic fault injections without fabricating deployment records, labeling active faults as CHANGE events.
- **InfrastructureAgent**: Queries Prometheus infrastructure and service health metrics, verifying service up/availability signals.
- **Parallel Fan-out / Fan-in**: IncidentManager fans out to 5 parallel agents (Log, Metrics, Trace, Deployment, Infrastructure), which converge into RCAAgent.
- **Strict Evidence Validation**: RCAAgent validates and filters LLM-generated evidence IDs against actually collected evidence IDs to prevent hallucinations.
- **AgentExecution Tracking**: All 7 agents (IncidentManager, LogAgent, MetricsAgent, TraceAgent, DeploymentAgent, InfrastructureAgent, RCAAgent) are persisted to the database.

### Limitations
- Phase 7 (Knowledge Base, RAG, pgvector, Historical Retrieval), Remediation, Risk Engine, and autonomous actions remain intentionally deferred.

## Phase 7 (Knowledge Base & RAG)
This phase introduces a historical knowledge base integration using PostgreSQL and pgvector. It adds a KnowledgeAgent to the LangGraph orchestration.

### Features
- **PostgreSQL pgvector**: Implemented pgvector for embeddings and similarity search.
- **Knowledge Agent**: Searches historical documentation and runbooks to provide additional context during investigation.
- **Knowledge Base Categories**: Dedicated directories and metadata for `incidents`, `runbooks`, and `postmortems`.
- **Deterministic Chunking & Ingestion**: Bounded, deterministic text chunking with stable deduplication during ingestion.
- **Retrieval API**: Robust `/knowledge/ingest` and `/knowledge/query` endpoints supporting `service` and `doc_type` filtering.
- **Knowledge Agent**: Searches historical documentation using `affected_service`, `incident_context`, `fault_type`, and existing evidence, returning explicit chunk IDs and similarity scores.
- **RCA Agent Enhancement**: RCA agent now consumes the historical runbooks retrieved by the KnowledgeAgent to reduce hallucinations and provide accurate remediations.

### Limitations
- Remediations, Risk Engine, and autonomous actions remain intentionally deferred.
