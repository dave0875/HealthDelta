Issue: #239
Title: Separate Fitness and Clinical domains in iPhone dashboard

Objective
- Introduce a clear Combined / Fitness / Clinical structure in the iPhone dashboard.
- Keep the experience bedside-friendly rather than technical.
- Make the current iPhone HealthKit permission boundary explicit and honest.

Acceptance anchors
- The main iPhone care screen exposes Combined, Fitness, and Clinical sections.
- When only HealthKit wellness data is present, the Clinical section shows a clear empty state rather than pretending clinical content exists.
- Local and ORIN-backed insights are assigned to sections using deterministic logic.
- The app clearly states that Apple Health data becomes available only after the user grants read access for the supported HealthKit types.
- CI and release proof remain green.
