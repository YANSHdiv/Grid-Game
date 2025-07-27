# 🐅 Human-Tiger Simulation Game 🎮

An AI-powered grid-based simulation where a human agent must collect food while avoiding a patrolling tiger agent. Designed using **Python**, **Tkinter**, and **Pygame**, this project demonstrates utility-based agents, Q-learning, and SARSA in a fun and interactive environment.

---

## 🧠 Key Features

- 👤 **Human Agent** can move through grid **edges and corners** (8 directions).
- 🐅 **Tiger Agent** guards food and patrols via **edge-only movement** (4 directions).
- 🍎 **Food Items** are placed randomly and must be collected by the human.
- 🛡️ **Safe Zones** protect the human temporarily (1-second invincibility).
- ⚡ **Power-Ups** to enhance movement or escape.
- 👁️ Tiger has **field of view** — will chase if it "sees" the human in adjacent tiles.
- 📊 Implements **Q-learning** and **SARSA** for adaptive behavior.

---

## 🖥️ Technologies Used

- Python 3.x
- Tkinter (for UI)
- Pygame (for rendering & game loop)
- Threading (for parallel execution)
- Custom environment logic

