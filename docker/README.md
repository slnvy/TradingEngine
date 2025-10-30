# monitoring stack

this directory contains the docker setup for the market maker monitoring infrastructure:

- **prometheus**: metrics collection
- **grafana**: dashboard visualization  
- **redis**: state storage

## quick start

1. start the stack:
   ```bash
   cd docker
   docker-compose up -d
   ```

2. access grafana dashboard:
   - url: http://localhost:3000
   - login: admin/admin
   - dashboard: "market maker dashboard"

3. verify prometheus is scraping:
   - url: http://localhost:9090
   - targets: http://localhost:9090/targets

## dashboard panels

the grafana dashboard includes:

- **current p&l**: real-time trading pnl in usdt
- **current inventory**: current btc position 
- **engine latency**: p95 and p50 latency of engine loops
- **outstanding orders**: buy and sell order counts

## metrics source

metrics are scraped from the live engine healthcheck endpoint at `http://host.docker.internal:8000/metrics`

## testing

to test the dashboard with live data:

1. start the monitoring stack
2. run the live engine with metrics enabled
3. verify data appears in grafana

the dashboard refreshes every 5 seconds and shows the last 5 minutes of data by default. 