# Nginx Load Balancer App 🚀

![Docker](https://img.shields.io/badge/Docker-multi--container-blue)
![Nginx](https://img.shields.io/badge/Nginx-load--balancer-green)
![Docker Compose](https://img.shields.io/badge/Docker_Compose-orchestration-orange)
![Linux](https://img.shields.io/badge/Linux-Ubuntu-yellow)

Production-like DevOps project demonstrating load balancing with Nginx and multiple backend containers using Docker Compose.

---

## 📌 Overview

This project demonstrates how to build a scalable backend architecture using:

- multiple application containers
- Nginx as a reverse proxy and load balancer
- Docker Compose for orchestration

---

## Open in browser
http://31.59.121.178:8080/

---

## 🧠 Architecture
```bash
Client (Browser)
↓
Nginx
↓
┌─────────────┐
│    │
app1 app2

```
---

## ⚙️ Tech Stack

- Python (Flask)
- Docker
- Docker Compose
- Nginx
- Linux (Ubuntu VPS)

---

## 🚀 Features

- Multi-container architecture
- Load balancing between backend services
- Reverse proxy configuration
- Scalable service simulation
- Container networking via Docker Compose

---

## 🔄 How It Works

- Nginx receives incoming requests
- Requests are forwarded to backend services
- Traffic is distributed between multiple containers
- Each container responds independently

---

## 🧠 What I Practiced
- Docker multi-container architecture
- Service orchestration with Docker Compose
- Load balancing concepts
- Reverse proxy configuration
- Backend scaling fundamentals