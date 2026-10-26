# Zerro-R portal addition

The access selection screen after successful login now has three cards:
1. Internal Workspace (unchanged)
2. Partner Portal (unchanged)
3. Zerro-R — inspections, quality assurance, compliance and reports across Civil, Mechanical, Piping, Electrical, Instrumentation, NDT and Commissioning.

Clicking Zerro-R navigates the current browser tab to https://zerroqa.flagestrator.com. Authentication is managed independently by the destination application; this change does not implement cross-domain single sign-on.

## Deploy
Unzip so your project's frontend folder contains package.json, src, public and Dockerfile. From the directory containing docker-compose.yml, rebuild using `docker compose up -d --build frontend` (adjust service name if different).
