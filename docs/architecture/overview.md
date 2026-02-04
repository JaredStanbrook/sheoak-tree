# System Overview

**Sheoak Tree** is a hardware monitoring and control system designed to run on embedded Linux devices (Raspberry Pi). It combines a real-time web dashboard with autonomous background services for hardware orchestration, network presence detection, and system health monitoring.

## Core Responsibilities

1.  **Hardware Abstraction:** interacting with physical GPIO pins, sensors, and relays.
2.  **State Management:** Maintaining a real-time view of the physical world (doors, motion, temperature).
3.  **Presence Detection:** Scanning the local network to determine occupancy.
4.  **User Interface:** Serving a Flask-based web UI and SSE real-time stream.

## High-Level Architecture

The system follows a **Service-Oriented Monolith** pattern within a single Python process.

```mermaid
graph TD
    User[User / Web Browser] <--> Nginx
    Nginx <--> FlaskApp[Flask Web Application]
    
    subgraph "Application Runtime"
        FlaskApp
        ServiceMgr[ServiceManager (Singleton)]
        
        ServiceMgr --> HW[HardwareManager]
        ServiceMgr --> Sys[SystemMonitor]
        ServiceMgr --> Pres[PresenceMonitor]
    end
    
    subgraph "Infrastructure"
        DB[(SQLite / SQLAlchemy)]
        GPIO[Physical GPIO Pins]
        Network[Local Network / ARP]
    end

    HW --> GPIO
    HW --> DB
    Pres --> Network
    Pres --> DB
    Sys --> DB

```

## Component Roles

### 1. The Web Application (Flask)

* **Role:** Handles HTTP requests, renders templates, and streams SSE updates.
* **Constraint:** It is the *consumer* of system state, not the *owner*. It queries the `HardwareManager` for state; it does not touch GPIO pins directly.

### 2. ServiceManager

* **Role:** The central registry and lifecycle controller.
* **Responsibility:** It holds references to all background services. It is responsible for calling `start()` on boot and `stop()` on shutdown. It ensures deterministic startup order.

### 3. Background Services

* **Role:** Autonomous workers that perform the system's actual work (polling sensors, scanning network).
* **Architecture:** All services inherit from `BaseService` or `ThreadedService`. They run in dedicated threads managed by the application process.

### 4. Hardware Strategies

* **Role:** The "Driver Layer." Strategies abstract the specific implementation details of a device (e.g., `GpioBinaryStrategy`, `GpioRelayStrategy`) from the business logic.
