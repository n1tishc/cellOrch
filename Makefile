.PHONY: up down test seed logs fmt

up:            ## build + run the whole stack
	docker compose up --build

down:          ## stop and remove containers
	docker compose down

test:          ## run the engine test suite
	cd orchestrator && python -m pytest -q

seed:          ## add 10 more runs to a running orchestrator
	curl -s -X POST "http://localhost:8000/seed?n=10" && echo

logs:          ## tail orchestrator logs
	docker compose logs -f orchestrator
