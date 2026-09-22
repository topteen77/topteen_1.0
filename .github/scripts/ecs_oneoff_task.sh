#!/usr/bin/env bash
# Run one throwaway ECS task from the NEW image, wait for it, print its logs.
#
# Cloned from the STEP 6 migrate block so other steps (collectstatic) can reuse
# the same capacity-provider / awsvpc / logging plumbing without touching migrate.
#
#   ecs_oneoff_task.sh <family-suffix> <shell-command> <label>
#
# Requires in the environment: ECS_CLUSTER, ECS_MIGRATE_SERVICE, IMAGE_URI
# Optional: ECS_LAUNCH_TYPE (fallback when the service has no capacity provider)
set -euo pipefail

FAMILY_SUFFIX="${1:?family suffix required}"
RUN_CMD="${2:?command required}"
LABEL="${3:-one-off task}"

fail_step() {
  echo "[FAIL] ${LABEL} — $1"
  echo "What failed : $2"
  echo "Hint        : $3"
  echo "Traffic     : previous ECS image still serving (services were NOT updated)"
  exit 1
}

[ -n "${IMAGE_URI:-}" ] || fail_step "missing image digest" "build job output empty" "Re-run from STEP 0"

SVC_JSON="$(aws ecs describe-services --cluster "${ECS_CLUSTER}" --services "${ECS_MIGRATE_SERVICE}")"
echo "${SVC_JSON}" | jq -e '.services[0].status == "ACTIVE"' >/dev/null \
  || fail_step "source service missing" "${ECS_MIGRATE_SERVICE} on ${ECS_CLUSTER}" \
    "Set vars.ECS_MIGRATE_SERVICE=topteen-web-service"

CURRENT_TD="$(echo "${SVC_JSON}" | jq -r '.services[0].taskDefinition')"
TD_JSON="$(aws ecs describe-task-definition --task-definition "${CURRENT_TD}" --query 'taskDefinition')"
CONTAINER_NAME="$(echo "${TD_JSON}" | jq -r '.containerDefinitions[0].name')"
FAMILY="$(echo "${TD_JSON}" | jq -r '.family')"
echo "source task def : ${CURRENT_TD}"
echo "container       : ${CONTAINER_NAME}"

ONEOFF_TD="$(echo "${TD_JSON}" | jq --arg IMAGE "${IMAGE_URI}" \
  --arg FAMILY "${FAMILY}-${FAMILY_SUFFIX}" --arg cmd "${RUN_CMD}" '
  del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities,
      .registeredAt, .registeredBy, .deregisteredAt)
  | .family = $FAMILY
  | .containerDefinitions[0].image = $IMAGE
  | .containerDefinitions[0].command = ["/bin/sh","-c",$cmd]
  | .containerDefinitions |= map(del(.healthCheck) | .essential = true)
')"

echo "${ONEOFF_TD}" > "/tmp/${FAMILY_SUFFIX}-task-def.json"
REGISTERED="$(aws ecs register-task-definition --cli-input-json "file:///tmp/${FAMILY_SUFFIX}-task-def.json")"
ONEOFF_TD_ARN="$(echo "${REGISTERED}" | jq -r '.taskDefinition.taskDefinitionArn')"
echo "registered td   : ${ONEOFF_TD_ARN}"

NETWORK_MODE="$(echo "${TD_JSON}" | jq -r '.networkMode // "bridge"')"
RUN_ARGS=( --cluster "${ECS_CLUSTER}" --task-definition "${ONEOFF_TD_ARN}" --count 1 )
CP="$(echo "${SVC_JSON}" | jq -c '.services[0].capacityProviderStrategy // []')"
LT="$(echo "${SVC_JSON}" | jq -r '.services[0].launchType // empty')"
if [ "${CP}" != "[]" ] && [ "${CP}" != "null" ]; then
  while IFS= read -r item; do
    RUN_ARGS+=( --capacity-provider-strategy "${item}" )
  done < <(echo "${CP}" | jq -r '.[] | "capacityProvider=\(.capacityProvider),weight=\(.weight // 1),base=\(.base // 0)"')
elif [ -n "${LT}" ]; then
  RUN_ARGS+=( --launch-type "${LT}" )
else
  RUN_ARGS+=( --launch-type "${ECS_LAUNCH_TYPE:-EC2}" )
fi
if [ "${NETWORK_MODE}" = "awsvpc" ]; then
  NET="$(echo "${SVC_JSON}" | jq -c '.services[0].networkConfiguration.awsvpcConfiguration')"
  [ "${NET}" != "null" ] || fail_step "awsvpc network missing on ${ECS_MIGRATE_SERVICE}" \
    "networkConfiguration" "Set subnets/security groups on the web service"
  SUBNETS="$(echo "${NET}" | jq -r '.subnets | join(",")')"
  SGS="$(echo "${NET}" | jq -r '.securityGroups | join(",")')"
  PUB="$(echo "${NET}" | jq -r '.assignPublicIp // "DISABLED"')"
  RUN_ARGS+=( --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SGS}],assignPublicIp=${PUB}}" )
fi

echo "aws ecs run-task ..."
RUN_OUT="$(aws ecs run-task "${RUN_ARGS[@]}" --overrides "$(jq -nc --arg n "${CONTAINER_NAME}" \
  '{containerOverrides:[{name:$n}]}')")" || fail_step "run-task API failed" "aws ecs run-task" \
  "Check iam:PassRole, cluster capacity, and that EC2 instances are registered"
echo "${RUN_OUT}" | jq '.failures'
FAIL_COUNT="$(echo "${RUN_OUT}" | jq '.failures | length')"
[ "${FAIL_COUNT}" = "0" ] || fail_step "run-task reported failures" \
  "$(echo "${RUN_OUT}" | jq -r '.failures')" \
  "RESOURCE:* = no EC2 capacity; AGENT = ecs agent; USER = IAM PassRole"
TASK_ARN="$(echo "${RUN_OUT}" | jq -r '.tasks[0].taskArn')"
[ -n "${TASK_ARN}" ] && [ "${TASK_ARN}" != "null" ] || fail_step "no task ARN" "${RUN_OUT}" "See failures above"
echo "task            : ${TASK_ARN}"

echo "Waiting for task to stop..."
aws ecs wait tasks-stopped --cluster "${ECS_CLUSTER}" --tasks "${TASK_ARN}" \
  || fail_step "wait tasks-stopped timed out" "${TASK_ARN}" "Check ECS Tasks tab and CloudWatch logs"

DESC="$(aws ecs describe-tasks --cluster "${ECS_CLUSTER}" --tasks "${TASK_ARN}")"
echo "${DESC}" | jq '.tasks[0] | {lastStatus, stoppedReason, stopCode}'
EXIT_CODE="$(echo "${DESC}" | jq -r '.tasks[0].containers[0].exitCode // 1')"
STOPPED_REASON="$(echo "${DESC}" | jq -r '.tasks[0].stoppedReason // ""')"

LOG_CFG="$(echo "${TD_JSON}" | jq -c '.containerDefinitions[0].logConfiguration // empty')"
if [ -n "${LOG_CFG}" ]; then
  LOG_GROUP="$(echo "${LOG_CFG}" | jq -r '.options["awslogs-group"] // empty')"
  LOG_PREFIX="$(echo "${LOG_CFG}" | jq -r '.options["awslogs-stream-prefix"] // empty')"
  TASK_ID="${TASK_ARN##*/}"
  STREAM="${LOG_PREFIX}/${CONTAINER_NAME}/${TASK_ID}"
  echo "---- last logs (${LOG_GROUP} ${STREAM}) ----"
  aws logs get-log-events --log-group-name "${LOG_GROUP}" --log-stream-name "${STREAM}" \
    --limit 120 --query 'events[].message' --output text 2>/dev/null || echo "(could not read logs)"
  echo "---- end logs ----"
fi

[ "${EXIT_CODE}" = "0" ] || fail_step "task exitCode=${EXIT_CODE}" \
  "stoppedReason=${STOPPED_REASON}" \
  "Fix from the logs above. Services were not updated."
echo "[OK] ${LABEL} — finished (exitCode 0)"
