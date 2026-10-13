MMAUG | 17 October 2026 | Python -> Docker -> Terraform
=====================================================
OCTOBER 17: LOCAL LAB FIRST. Python, Docker and Terraform foundations.
OCTOBER 27: Azure architecture, advanced CI/CD and DevSecOps in ../docs.
Detailed pipeline configuration and the CodeQL workshop are not October 17 labs.
This Flask API uses Gunicorn in Docker. app.py's local server is development-only.
No AI model, user authentication or database is included.
Required: Python 3.10+, Docker Engine or Docker Desktop (running, Linux
containers), Terraform 1.5+ but below 2.0, curl, and internet for first pulls/init.
Docker Desktop licensing may apply. Docker socket access is privileged.

All commands start in this launchpad-lab directory. Use two terminals when a
server runs in the foreground. Bash/zsh commands are shown first.

1. PYTHON
   python3 --version
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   python -m unittest -v
   python app.py

   In a second terminal:
   curl -fsS http://127.0.0.1:8000/health
   curl -fsS "http://127.0.0.1:8000/sum?values=5,10,15"
   curl -i "http://127.0.0.1:8000/sum?values=5,nope,15"
   Expected: {"status": "ok"}, then {"total": 30, "average": 10.0},
   then HTTP 400 and a JSON error. Stop the Python server with Ctrl+C.
   The test suite has 11 methods. Browser interface: http://127.0.0.1:8000/ui

2. DOCKER
   docker version
   docker info
   docker build -t mmaug-launchpad:1.0 .
   docker run -d --name mmaug-launchpad-manual -p 127.0.0.1:8080:8000 -e "APP_MESSAGE=Hello from Docker!" mmaug-launchpad:1.0
   curl -fsS http://127.0.0.1:8080/
   curl -fsS "http://127.0.0.1:8080/sum?values=5,10,15"
   docker logs mmaug-launchpad-manual
   docker inspect --format '{{.State.Health.Status}}' mmaug-launchpad-manual
   Wait up to approximately 35 seconds for the health check. Inspect health
   details if it stays unhealthy:
   docker inspect --format '{{json .State.Health}}' mmaug-launchpad-manual
   docker exec mmaug-launchpad-manual id
   Expected: greeting from Docker; total 30; healthy; uid=10001(app).
   docker stop mmaug-launchpad-manual
   docker rm mmaug-launchpad-manual

   OPTIONAL COMPOSE COMPARISON (from launchpad-lab, before Terraform):
   docker compose config
   docker compose -p mmaug-launchpad-lab up -d --build
   curl -fsS http://127.0.0.1:8090/health
   curl -fsS http://127.0.0.1:8090/
   docker compose -p mmaug-launchpad-lab logs
   docker compose -p mmaug-launchpad-lab down
   Compose uses host port 8090 and its own project-scoped container.
   Bring it down before continuing. Do not manage it with Terraform.
   Docker Compose v2 is required only for this optional comparison.

3. TERRAFORM (requires the locally built image from step 2)
   Terraform creates two managed resources: the image reference and container.
   The provider uses the local image if available. Without it, Terraform may
   attempt a registry pull and fail. Rebuild it before planning.
   cd terraform
   export DOCKER_HOST="$(docker context inspect --format '{{.Endpoints.docker.Host}}')"
   terraform init
   terraform fmt -check
   terraform validate
   terraform plan -out=launchpad.tfplan
   Read the plan: initially 2 to add, 0 to change, 0 to destroy.
   terraform apply launchpad.tfplan
   terraform output -raw app_url
   curl -fsS http://127.0.0.1:8080/health
   curl -fsS http://127.0.0.1:8080/
   Expected greeting: Hello from Terraform!
   terraform state list
   terraform plan
   Expected: No changes (provided no drift occurred).

4. CONTROLLED CHANGE
   terraform plan -var="host_port=8081" -out=change.tfplan
   The port change should replace the container. Read the actual plan.
   terraform apply change.tfplan
   curl -fsS http://127.0.0.1:8081/health
   Keep using -var="host_port=8081" on subsequent plans, or update the default
   in main.tf to 8081. Otherwise Terraform will propose moving back to 8080.

5. SCOPED CLEANUP
   terraform plan -destroy -var="host_port=8081" -out=cleanup.tfplan
   Review that only this lab's two Terraform resources are being removed.
   terraform apply cleanup.tfplan
   terraform state list
   docker ps -a --filter name=mmaug-launchpad-iac
   cd ..
   docker image rm mmaug-launchpad:1.0
   keep_locally=true keeps the image during Terraform destroy; the last command
   removes only this named image. Do not run docker system prune in this lab.
   If you skipped step 4, omit its host_port variable in cleanup.
   Do not delete Terraform state before destroying its resources.

WINDOWS POWERSHELL
   Use py -3 instead of python3 to create the venv:
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   If activation is blocked, use .\.venv\Scripts\python.exe directly.
   Use curl.exe instead of curl for the HTTP examples.
   Set Docker endpoint in Terraform's terminal:
   $env:DOCKER_HOST = docker context inspect --format '{{.Endpoints.docker.Host}}'
   The local Docker context must target Linux containers.
   Set application configuration with $env:APP_MESSAGE = "Hello!"
   Bash example: APP_MESSAGE="Hello!" python app.py
   Docker and Terraform single-line commands work in both shells.

TROUBLESHOOTING
   Cannot connect to daemon: start Docker Desktop/Engine, rerun docker info.
   Wrong Terraform endpoint: rerun the context/DOCKER_HOST command in the same
   terminal as Terraform. Never change the context of unrelated workloads.
   Port allocated: stop only the lab container, or choose host_port=8081.
   Docker connection refused: verify -p and inspect logs; app binds 0.0.0.0.
   Local Python Address already in use: Ctrl+C the original server, or run
   PORT=8001 python app.py and change the local curl URL accordingly.
   Registry pull denied: run docker image inspect mmaug-launchpad:1.0;
   return to this directory and rebuild the image if missing.
   Formatting check fails: terraform fmt, then terraform fmt -check.
   Invalid /sum input: exactly three comma-separated integers, quoted URL.
   Credentials, state, saved plans and .env files are not teaching screenshots.

SOURCE REFERENCES
   See ../docs/01-python-explained.md for every Python function and test.
   See ../docs/03-terraform-azure.md for modules, import and Azure Blob backend.
   OCTOBER 27 WORKSHOPS:
   See ../docs/04-pipelines.md for advanced delivery, approvals and verification.
   See ../docs/05-devsecops-codeql.md for DevSecOps and source-scanning policy.
   Repository scans remain enabled; these dates govern teaching, not triggers.
   https://docs.python.org/3/tutorial/
   https://docs.python.org/3/library/http.server.html
   https://docs.docker.com/get-started/
   https://docs.docker.com/reference/dockerfile/
   https://developer.hashicorp.com/terraform/tutorials/docker-get-started
   https://registry.terraform.io/providers/kreuzwerker/docker/latest/docs
