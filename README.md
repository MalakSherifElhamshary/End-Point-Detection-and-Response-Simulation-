# Endpoint Detection and Response (EDR) Simulation

A machine learning-based Endpoint Detection and Response (EDR) simulation designed to monitor endpoint activity, detect suspicious behavior, and support automated security analysis.

The project simulates the core functionality of an EDR solution by collecting endpoint events, analyzing system activity, detecting anomalies, and presenting security-related information through a web-based dashboard.

---

## 📌 Overview

Endpoint Detection and Response (EDR) solutions continuously monitor endpoint activities to identify suspicious behavior and potential security threats.

This project provides a simplified EDR simulation that demonstrates how endpoint data can be collected, analyzed, and used to detect potentially malicious activity.

The system focuses on:

- Endpoint activity monitoring
- Log collection and analysis
- Anomaly detection
- Machine Learning-based threat detection
- Security event visualization
- Automated detection workflows

---

## 🏗️ System Architecture

The system consists of the following main components:

### 1. Endpoint Agent

The agent is responsible for monitoring endpoint activity and collecting relevant security events.

```text
Endpoint Activity
        │
        ▼
   EDR Agent
        │
        ▼
 Event Collection
        │
        ▼
 Log Processing
        │
        ▼
 Detection Model
        │
        ▼
 Threat Analysis
