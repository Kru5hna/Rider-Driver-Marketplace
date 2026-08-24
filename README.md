# Rider–Driver Matching Marketplace (Distributed System)

> A high-concurrency, resilience-tested, microservices-based dispatch and matching platform built with **Python (FastAPI), gRPC, MySQL, Docker, Kubernetes, Prometheus, Grafana, and k6**.

---

## 🎯 1. Project Overview & Strategic Architecture

### The Problem
Traditional monolithic backend applications struggle under high-concurrency ride-hailing demand (e.g., thousands of simultaneous rider requests per second). A failure in one domain (e.g., pricing calculation) can bring down the entire dispatch lifecycle. Furthermore, matching drivers to riders under high concurrency introduces **race conditions** (two riders assigned the same driver) and **duplicate request creation** during network retries.

### The Solution: A True 3-Service Marketplace Architecture
We are building **Uber's Core Engineering Architecture**:

1. **Dispatch Service (REST API Gateway & State Machine):** Exposes `/trips/request`, `/trips/{id}`, enforces **idempotency** via `Idempotency-Key` headers, and manages trip lifecycle states in MySQL.
2. **Matching Service (Spatial Candidate Search & Concurrency Safety):** Finds nearby available drivers using spatial grid partitioning ($O(K)$ candidate lookup), and performs **atomic driver reservation** using optimistic locking / conditional SQL updates.
3. **Pricing Service (Stateless gRPC Microservice):** Computes dynamic fares over high-performance **gRPC (HTTP/2 + Protobuf)**.
4. **Trip Ledger (MySQL DB):** ACID-compliant relational store tracking trips, driver availability, and event history.
5. **Kubernetes Orchestration:** Containerized deployments running with automated pod replication, self-healing (`livenessProbe`/`readinessProbe`), and service discovery.
6. **Observability & Chaos Proof:** Instrumented with **Prometheus RED metrics** (Rate, Errors, Duration) and **Grafana dashboards**, proven resilient via **k6 load testing** and **pod-termination chaos engineering**.

---

## 🏗️ 2. High-Level System Architecture

```text
                               ┌─────────────────────────────┐
                               │    LOAD GENERATOR (k6)      │
                               │  Simulates 500 req/sec      │
                               └──────────────┬──────────────┘
                                              │ HTTP / REST (Idempotency-Key)
                                              ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                 KUBERNETES CLUSTER                                       │
│                                                                                          │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│   │ DISPATCH SERVICE PODS (FastAPI) (Replicas: 2+)                                   │   │
│   │  • Endpoint: POST /trips/request (Idempotent)                                    │   │
│   │  • Prometheus RED Metrics Exporter (:8000/metrics)                               │   │
│   └───────────────┬─────────────────────────┬─────────────────────────┬──────────────┘   │
│                   │                         │                         │                  │
│                   │ gRPC                    │ internal gRPC / REST    │ SQL Queries      │
│                   │ (Port 50051)            │ (Port 50052)            │ (Port 3306)      │
│                   ▼                         ▼                         ▼                  │
│   ┌───────────────────────────────┐ ┌───────────────────────────────┐ ┌──────────────────┐ │
│   │ PRICING SERVICE POD           │ │ MATCHING SERVICE POD          │ │ MYSQL DB POD     │ │
│   │ (Python gRPC Server)          │ │ (Spatial Grid + Atomic Lock)  │ │ (Trips & Drivers)│ │
│   │                               │ │                               │ │                  │ │
│   │  • Fast fare calculation      │ │  • Spatial driver search      │ │ • ACID State     │ │
│   │  • Pure stateless RPC         │ │  • Concurrency-safe reserve   │ │ • Idempotency Log│ │
│   └───────────────────────────────┘ └───────────────────────────────┘ └──────────────────┘ │
│                                                                                          │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│   │ OBSERVABILITY STACK                                                              │   │
│   │  • Prometheus (Scrapes metrics from Dispatch, Pricing, and Matching)             │   │
│   │  • Grafana (Visualizes latency histograms, active trips & error rates)           │   │
│   └──────────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 💡 3. Deep Engineering Principles & Algorithms

### 3.1 Spatial Grid Driver Matching (DSA)
- **Problem:** Scanned $N$ drivers across the entire database is an $O(N)$ operation per request, causing massive database bottlenecks at 1,000,000 drivers.
- **Solution:** Partition geographical coordinates into spatial grid cells (Geohash / H3 concept). The matching engine only queries drivers in the **rider's current cell + 8 neighboring cells**, reducing candidate search space from $O(N)$ to $O(K)$.

### 3.2 Race Condition Prevention (Concurrency Control)
- **Problem:** Two riders request a ride simultaneously near Driver #42 (`status = 'AVAILABLE'`). Both requests see Driver #42 as available and attempt assignment, creating a double-booking bug.
- **Solution:** Atomic conditional update in database:
  ```sql
  UPDATE drivers 
  SET status = 'MATCHED' 
  WHERE id = 42 AND status = 'AVAILABLE';
  ```
  If `affected_rows == 1`, reservation succeeds. If `0`, another request claimed Driver #42, and the engine fails over to candidate #2.

### 3.3 Idempotency (`Idempotency-Key` Header)
- **Problem:** Network timeout causes rider app to retry `POST /trips/request`, accidentally creating duplicate trips (#1001 and #1002).
- **Solution:** Dispatch service checks an `idempotency_keys` table. If the key exists, it immediately returns the existing trip record without re-running matching or charging pricing.

---

## ⚡ 4. Technology Stack & Protocols

| Component | Technology | Protocol / Port | Purpose |
| :--- | :--- | :--- | :--- |
| **Dispatch Service** | Python 3.11 + FastAPI | HTTP/1.1 (Port 8000) | REST Gateway, Idempotency & Trip Lifecycle |
| **Matching Service** | Python 3.11 | gRPC / REST (Port 50052) | Spatial Grid Lookup & Atomic Driver Lock |
| **Pricing Service** | Python 3.11 + gRPC | gRPC / HTTP/2 (Port 50051) | Dynamic Fare Engine |
| **Contract Schema** | Protocol Buffers (v3) | Binary Payload | High-speed Inter-service RPC Contracts |
| **Database** | MySQL 8.0 | TCP (Port 3306) | Relational Ledger for Trips, Drivers & Idempotency |
| **Containerization** | Docker | Docker Engine | Container Packaging & Isolation |
| **Orchestration** | Kubernetes | K8s Cluster | Pod Replication, Rolling Updates, Self-Healing |
| **Metrics Scraper** | Prometheus | HTTP (Port 9090) | Time-series RED Metrics Collection |
| **Visualization** | Grafana | HTTP (Port 3000) | Observability & Latency Histogram Dashboards |
| **Load Generator** | k6 | HTTP Load Generator | Concurrency & Stress Testing |

---

## 🗺️ 5. 8-Level Mastery Roadmap

```text
Level 1: Basic Backend (FastAPI + MySQL + REST)
  ├── Level 2: Service Architecture (Dispatch + Pricing + gRPC + Protobuf)
  │     ├── Level 3: Real Marketplace (Matching Engine + Spatial Grid + Driver State)
  │     │     ├── Level 4: Concurrency & Idempotency (Atomic Locks + Idempotency-Key)
  │     │     │     ├── Level 5: Kubernetes Infrastructure (Replicas + Health Probes)
  │     │     │     │     ├── Level 6: Observability (Prometheus + Grafana RED Metrics)
  │     │     │     │     │     ├── Level 7: Load Testing (k6 RPS Latency Curve)
  │     │     │     │     │     └── Level 8: Chaos Engineering (Pod Termination Proof)
```

---

## 📁 6. Repository File Structure

```text
Rider Driver Marketplace/
├── README.md                   # Complete System Architecture & Engineering Spec
├── docker-compose.yml          # Local MySQL Database container configuration
├── proto/
│   ├── pricing.proto           # gRPC Pricing contract definition
│   ├── matching.proto          # gRPC Matching contract definition
│   ├── pricing_pb2.py          # Auto-generated Protobuf classes
│   └── pricing_pb2_grpc.py     # Auto-generated gRPC stubs
├── services/
│   ├── dispatch/               # Main REST Gateway & Trip Lifecycle
│   │   ├── db.py               # SQLAlchemy models (trips, drivers, idempotency_keys)
│   │   └── main.py             # FastAPI REST endpoints + gRPC client logic
│   ├── matching/               # Matching Engine Microservice
│   │   └── engine.py           # Spatial grid search & atomic driver reservation
│   └── pricing/                # Fare Calculation Service
│       └── server.py           # gRPC pricing server implementation
└── k8s/                        # Kubernetes Deployment & Service manifests
```
