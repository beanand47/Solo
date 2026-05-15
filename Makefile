test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=. --cov-report=term-missing --cov-report=html

test-auth:
	pytest tests/test_auth.py -v

test-tasks:
	pytest tests/test_tasks.py -v

lint:
	python -m py_compile main.py routers/*.py services/*.py models.py database.py

run:
	uvicorn main:app --reload

worker:
	rq worker solo_tasks

css:
	npm run build:css

css-watch:
	npm run watch:css

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down
