# Unix/macOS：make deploy
.PHONY: deploy stop logs logs-nginx

deploy:
	@chmod +x deploy.sh 2>/dev/null || true
	@./deploy.sh

stop:
	docker compose down

logs:
	docker compose logs -f app

logs-nginx:
	docker compose logs -f gateway
