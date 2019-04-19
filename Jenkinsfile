pipeline {
  agent any

  environment {
    // Necessary so that `docker login` credentials are not put in shared location
    HOME = "${env.WORKSPACE}"
    DOCKER_REGISTRY = 'docker.chameleoncloud.org'
    DOCKER_REGISTRY_CREDS = credentials('kolla-docker-registry-creds')
    LABEL = "${env.GIT_COMMIT}"
  }

  stages {
    stage('docker-setup') {
      steps {
        sh 'docker login --username=$DOCKER_REGISTRY_CREDS_USR --password=$DOCKER_REGISTRY_CREDS_PSW $DOCKER_REGISTRY'
      }
    }

    stage('build-and-publish') {
      steps {
        sh 'make build_prometheus-openstack-exporter'
        sh 'make publish_prometheus-openstack-exporter'
      }
    }
  }

  post {
    always {
      sh 'docker logout $DOCKER_REGISTRY'
    }

    failure {
      slackSend(
        channel: "#notifications",
        message: "*Build* of *${env.JOB_NAME}* (${env.LABEL}) failed. <${env.RUN_DISPLAY_URL}|View build log>",
        color: "danger"
      )
    }

    success {
      slackSend(
        channel: "#notifications",
        message: "*Build* of *${env.JOB_NAME}* (${env.LABEL}) completed successfuly. <${env.RUN_DISPLAY_URL}|View build log>",
        color: "good"
      )
      build job: 'ansible-playbook', wait: false, parameters: [
        string(name: 'PLAYBOOK_NAME', value: 'prometheus'),
        string(name: 'JENKINS_AGENT_LABEL', value: 'ansible-uc-dev')
      ]
    }
  }
}
