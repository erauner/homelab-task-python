#!/usr/bin/env groovy
/**
 * Jenkinsfile for homelab-task-python
 *
 * Builds and pushes the Python task toolkit container image on every merge to main.
 * Uses semantic versioning based on git tags.
 *
 * Image: docker.nexus.erauner.dev/homelab/taskkit:<version>
 */

@Library('homelab') _

// Inline pod template with Python + Kaniko
def podYaml = '''
apiVersion: v1
kind: Pod
metadata:
  labels:
    workload-type: ci-builds
spec:
  imagePullSecrets:
  - name: nexus-registry-credentials
  containers:
  - name: jnlp
    image: jenkins/inbound-agent:3355.v388858a_47b_33-3-jdk21
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        cpu: 500m
        memory: 512Mi
  - name: python
    image: python:3.12-slim
    command: ['cat']
    tty: true
    resources:
      requests:
        cpu: 200m
        memory: 512Mi
      limits:
        cpu: 1000m
        memory: 1Gi
  - name: kaniko
    image: gcr.io/kaniko-project/executor:debug
    command: ['sleep', '3600']
    volumeMounts:
    - name: nexus-creds
      mountPath: /kaniko/.docker
    resources:
      requests:
        cpu: 500m
        memory: 1Gi
      limits:
        cpu: 1000m
        memory: 2Gi
  volumes:
  - name: nexus-creds
    secret:
      secretName: nexus-registry-credentials
      items:
      - key: config.json
        path: config.json
'''

pipeline {
    agent {
        kubernetes {
            yaml podYaml
        }
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 15, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    environment {
        IMAGE_NAME = 'docker.nexus.erauner.dev/homelab/taskkit'
    }

    stages {
        stage('Setup') {
            steps {
                container('python') {
                    sh '''
                        echo "=== Installing uv ==="
                        pip install uv --quiet

                        echo "=== Setting up PATH for uv ==="
                        export PATH="$HOME/.local/bin:$PATH"
                        which uv || echo "uv not found in PATH"

                        echo "=== Installing dependencies (including dev) ==="
                        uv sync --extra dev

                        echo "=== Python version ==="
                        python --version
                    '''
                }
            }
        }

        stage('Lint') {
            steps {
                container('python') {
                    sh '''
                        export PATH="$HOME/.local/bin:$PATH"
                        echo "=== Running ruff linter ==="
                        uv run ruff check src/ tests/

                        echo "=== Running ruff formatter check ==="
                        uv run ruff format --check src/ tests/
                    '''
                }
            }
        }

        stage('Test') {
            steps {
                container('python') {
                    sh '''
                        export PATH="$HOME/.local/bin:$PATH"
                        echo "=== Running tests ==="
                        uv run pytest tests/ -v --tb=short
                    '''
                }
            }
        }

        stage('Build Check') {
            steps {
                container('python') {
                    sh '''
                        export PATH="$HOME/.local/bin:$PATH"
                        echo "=== Verifying package build ==="
                        uv build

                        echo "=== Testing CLI entrypoint ==="
                        uv run task-run --help
                    '''
                }
            }
        }

        stage('Build and Push Image') {
            steps {
                script {
                    env.VERSION = homelab.gitDescribe()
                    env.COMMIT = homelab.gitShortCommit()
                    echo "Building image version: ${env.VERSION} (commit: ${env.COMMIT})"

                    // Build and push using shared library (versioned tag)
                    homelab.homelabBuild([
                        image: env.IMAGE_NAME,
                        version: env.VERSION,
                        commit: env.COMMIT,
                        dockerfile: 'Dockerfile',
                        context: '.'
                    ])
                }
            }
        }

        stage('Push Latest Tag') {
            steps {
                container('kaniko') {
                    sh """
                        /kaniko/executor \
                            --dockerfile=Dockerfile \
                            --context=dir://. \
                            --destination=${IMAGE_NAME}:latest \
                            --cache=true \
                            --cache-repo=${IMAGE_NAME}/cache \
                            --custom-platform=linux/amd64
                    """
                }
            }
        }
    }

    post {
        success {
            echo """
            ✅ Build successful!

            Docker Image: ${env.IMAGE_NAME}:${env.VERSION}
            Latest Tag:   ${env.IMAGE_NAME}:latest

            To pull: docker pull ${env.IMAGE_NAME}:latest
            """
        }
        failure {
            script {
                homelab.postFailurePrComment([repo: 'erauner/homelab-task-python'])
                homelab.notifyDiscordFailure()
            }
        }
    }
}
