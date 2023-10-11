dev.build:
	@docker-compose build pactman-dev;

dev.shell:
	@docker-compose run pactman-dev /bin/bash;
