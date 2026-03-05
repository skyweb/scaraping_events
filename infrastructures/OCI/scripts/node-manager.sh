#!/usr/bin/env bash
# node-manager.sh — Visualizza e gestisce i workload per nodo OKE
# Uso: ./node-manager.sh [status|stop|start|toggle|list] [servizio]
# Esempi:
#   ./node-manager.sh                      → report completo nodi + servizi
#   ./node-manager.sh stop sonarqube       → ferma sonarqube (scale 0)
#   ./node-manager.sh start sonarqube      → riavvia sonarqube (scale 1)
#   ./node-manager.sh toggle argocd-server → inverti lo stato
#   ./node-manager.sh stop-all-optional    → ferma tutti i tool dev/devops
#   ./node-manager.sh start-all-optional   → riavviali tutti

if [ -z "${BASH_VERSION:-}" ]; then
  echo "Errore: questo script richiede bash."
  echo "Usa: bash node-manager.sh  oppure  ./node-manager.sh"
  exit 1
fi

set -euo pipefail

# ─── colori ($'...' → escape reale, funziona con echo e printf %s) ───────────
BOLD=$'\033[1m';    RESET=$'\033[0m'
RED=$'\033[0;31m';  GREEN=$'\033[0;32m';  YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'; BLUE=$'\033[0;34m';   MAGENTA=$'\033[0;35m'; DIM=$'\033[2m'

# ─── nodi ────────────────────────────────────────────────────────────────────
NODE_HEAVY="10.0.1.13"
NODE_LIGHT="10.0.1.227"

# ─── catalogo servizi: "nome_logico ns kind nome_k8s" ────────────────────────
# Formato: <alias> <namespace> <kind> <nome-k8s>
SERVICE_CATALOG="
airflow-scheduler   airflow     deployment  airflow-scheduler
airflow-webserver   airflow     deployment  airflow-webserver
kong                apps        deployment  kong-kong
backstage           devs        deployment  backstage
sonarqube           devs        statefulset sonarqube-sonarqube
argocd-controller   argocd      statefulset argocd-application-controller
argocd-server       argocd      deployment  argocd-server
argocd-repo-server  argocd      deployment  argocd-repo-server
argocd-redis        argocd      deployment  argocd-redis
argocd-dex          argocd      deployment  argocd-dex-server
argocd-appset       argocd      deployment  argocd-applicationset-controller
postgres            database    statefulset postgres
minio               database    deployment  minio
grafana             monitoring  deployment  grafana
prometheus          monitoring  deployment  prometheus-server
loki                monitoring  statefulset loki
tempo               monitoring  statefulset tempo
alertmanager        monitoring  statefulset prometheus-alertmanager
traefik             traefik     deployment  traefik
oauth2-proxy        traefik     deployment  oauth2-proxy
k8s-dashboard       clusters    deployment  kubernetes-dashboard-web
velero              clusters    deployment  velero
"

# Servizi opzionali (non critici) — stop/start in blocco
OPTIONAL_SERVICES="sonarqube backstage argocd-controller argocd-server argocd-repo-server argocd-redis argocd-dex argocd-appset airflow-scheduler airflow-webserver loki tempo alertmanager k8s-dashboard velero"

# ─── barra grafica ───────────────────────────────────────────────────────────
# _bar <percentuale> <larghezza=14>
# Output: ██████████░░░░ 72%
_bar() {
  local pct="${1:-0}" width="${2:-14}"
  # rimuovi il simbolo % se presente e clamp 0-100
  pct="${pct//%/}"
  pct="${pct%%.*}"
  [ "$pct" -gt 100 ] && pct=100
  [ "$pct" -lt 0 ]   && pct=0

  local filled=$(( pct * width / 100 ))
  local empty=$(( width - filled ))

  local bar=""
  local i=0
  while [ $i -lt $filled ]; do bar="${bar}█"; i=$((i+1)); done
  while [ $i -lt $((filled + empty)) ]; do bar="${bar}░"; i=$((i+1)); done

  # colore in base alla soglia
  local color="$GREEN"
  [ "$pct" -ge 70 ] && color="$YELLOW"
  [ "$pct" -ge 90 ] && color="$RED"

  printf "${color}%s${RESET} %3d%%" "$bar" "$pct"
}

# ─── lookup: dato alias restituisce "ns kind k8s_name" ───────────────────────
_lookup() {
  local alias="$1"
  echo "$SERVICE_CATALOG" | awk -v a="$alias" '$1==a {print $2, $3, $4}' | head -1
}

_node_label() {
  [ "$1" = "$NODE_HEAVY" ] && echo "heavy" || echo "light"
}

_get_replicas() {
  kubectl get "$2" "$3" -n "$1" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0"
}

_scale() {
  kubectl scale "$2" "$3" -n "$1" --replicas="$4" 2>&1
}

# ─── status ──────────────────────────────────────────────────────────────────
cmd_status() {
  echo ""
  printf "%b\n" "${BOLD}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
  printf "%b\n" "${BOLD}║               OKE NODE MANAGER — events-oke (eu-milan-1)            ║${RESET}"
  printf "%b\n" "${BOLD}╚══════════════════════════════════════════════════════════════════════╝${RESET}"
  echo ""

  local node_metrics pod_metrics pods_json
  node_metrics=$(kubectl top nodes --no-headers 2>/dev/null || echo "")
  pod_metrics=$(kubectl top pods -A --no-headers 2>/dev/null || echo "")
  pods_json=$(kubectl get pods -A -o json 2>/dev/null)

  for node_ip in "$NODE_HEAVY" "$NODE_LIGHT"; do
    local label role_cpu role_mem
    label=$(_node_label "$node_ip")

    if [ "$label" = "heavy" ]; then
      role_cpu="3 vCPU / 2820m alloc"; role_mem="18 GB / 15.4 GB alloc"
      printf "%b\n" "${BOLD}${BLUE}▶ NODO HEAVY${RESET}  ${DIM}(${node_ip} — ${role_cpu} — ${role_mem})${RESET}"
    else
      role_cpu="1 vCPU / 840m alloc"; role_mem="6 GB / 4.4 GB alloc"
      printf "%b\n" "${BOLD}${MAGENTA}▶ NODO LIGHT${RESET}  ${DIM}(${node_ip} — ${role_cpu} — ${role_mem})${RESET}"
    fi

    # Metriche nodo
    local nline cpu_used cpu_pct mem_used mem_pct
    nline=$(echo "$node_metrics" | grep "^$node_ip " || echo "")
    cpu_used=$(echo "$nline" | awk '{print $2}'); cpu_pct=$(echo "$nline" | awk '{print $3}')
    mem_used=$(echo "$nline" | awk '{print $4}'); mem_pct=$(echo "$nline" | awk '{print $5}')

    # Allocazione da describe
    local alloc_line cpu_req mem_lim
    alloc_line=$(kubectl describe node "$node_ip" 2>/dev/null | grep -A8 "Allocated resources" || echo "")
    cpu_req=$(echo "$alloc_line"  | awk '/cpu/{print $2"  "$3}' | head -1)
    mem_lim=$(echo "$alloc_line"  | awk '/memory/{print $4"  "$5}' | head -1)

    # estrai solo le percentuali numeriche per le barre
    local cpu_pct_n mem_pct_n cpu_req_pct_n mem_lim_pct_n
    cpu_pct_n="${cpu_pct//%/}"; mem_pct_n="${mem_pct//%/}"
    cpu_req_pct_n=$(echo "$cpu_req" | grep -oE '\([0-9]+%\)' | tr -d '()%' || echo "0")
    mem_lim_pct_n=$(echo "$mem_lim" | grep -oE '\([0-9]+%\)' | tr -d '()%' || echo "0")

    printf "  ${BOLD}%-14s${RESET} %s  %s\n" \
      "CPU usata:" "$(    _bar "${cpu_pct_n:-0}")" "  ${DIM}${cpu_used:-?}${RESET}"
    printf "  ${BOLD}%-14s${RESET} %s  %s\n" \
      "RAM usata:" "$(    _bar "${mem_pct_n:-0}")" "  ${DIM}${mem_used:-?}${RESET}"
    printf "  ${BOLD}%-14s${RESET} %s  %s\n" \
      "CPU sched.:" "$(   _bar "${cpu_req_pct_n:-0}")" "  ${DIM}requests${RESET}"
    printf "  ${BOLD}%-14s${RESET} %s  %s\n" \
      "MEM limits:" "$(   _bar "${mem_lim_pct_n:-0}")" "  ${DIM}limits${RESET}"
    echo ""

    printf "  ${BOLD}%-36s %-16s %8s %8s %s${RESET}\n" "POD" "NAMESPACE" "CPU" "RAM" "STATO"
    printf "  %s\n" "────────────────────────────────────────────────────────────────────────────"

    # Lista pod su questo nodo (escludi kube-system daemonset e system)
    local pod_list
    pod_list=$(echo "$pods_json" | python3 -c "
import json, sys
target = '${node_ip}'
skip_ns    = {'kube-system','kube-node-lease','kube-public'}
skip_pfx   = ('kube-flannel','kube-proxy','proxymux','csi-oci','oke-dataplane',
               'oke-node-problem','loki-canary','otel-collector',
               'prometheus-prometheus-node-exporter','promtail')
for p in json.load(sys.stdin)['items']:
    if p['spec'].get('nodeName','') != target: continue
    ns = p['metadata']['namespace']
    if ns in skip_ns: continue
    name = p['metadata']['name']
    if any(name.startswith(s) for s in skip_pfx): continue
    phase = p['status'].get('phase','-')
    restarts = sum(c.get('restartCount',0) for c in p['status'].get('containerStatuses',[]))
    print(f'{ns}|{name}|{phase}|{restarts}')
" 2>/dev/null)

    printf '%s\n' "$pod_list" | while IFS='|' read -r ns pname phase restarts; do
      [ -z "$ns" ] && continue
      pcpu=$(printf '%s\n' "$pod_metrics" | awk -v n="$ns" -v p="$pname" '$1==n && $2==p {print $3}')
      pmem=$(printf '%s\n' "$pod_metrics" | awk -v n="$ns" -v p="$pname" '$1==n && $2==p {print $4}')
      pcpu="${pcpu:--}"; pmem="${pmem:--}"

      short=$(printf '%s' "$pname" | cut -c1-35)
      [ "${#pname}" -gt 35 ] && short="${short}..."

      sc="$GREEN"; sl="running"
      [ "$phase" != "Running" ] && { sc="$YELLOW"; sl="$phase"; }
      [ "${restarts:-0}" -gt 5 ] && { sc="$RED"; sl="⚠ rst:$restarts"; }

      printf "  %-36s ${DIM}%-16s${RESET} %8s %8s  ${sc}%s${RESET}\n" \
        "$short" "$ns" "$pcpu" "$pmem" "$sl"
    done

    echo ""
  done

  # ── Pannello toggle rapido ────────────────────────────────────────────────
  printf "%b\n" "${BOLD}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
  printf "%b\n" "${BOLD}║                    SERVIZI GESTIBILI (stop/start)                   ║${RESET}"
  printf "%b\n" "${BOLD}╚══════════════════════════════════════════════════════════════════════╝${RESET}"
  echo ""
  printf "  ${BOLD}%-22s %-12s %-28s %s${RESET}\n" "ALIAS" "STATO" "RISORSA" "TOGGLE"
  printf "  %s\n" "────────────────────────────────────────────────────────────────────────────"

  echo "$SERVICE_CATALOG" | awk 'NF==4' | sort -k1,1 | while read -r alias ns kind k8sname; do
    local replicas
    replicas=$(_get_replicas "$ns" "$kind" "$k8sname")
    local sc sl
    if [ "${replicas:-0}" -gt 0 ]; then sc="$GREEN"; sl="● on ($replicas)"; else sc="$RED"; sl="○ off"; fi
    printf "  %-22s ${sc}%-12s${RESET} %-28s ${DIM}./node-manager.sh toggle %s${RESET}\n" \
      "$alias" "$sl" "$ns/$k8sname" "$alias"
  done

  echo ""
  printf "%b\n" "  ${DIM}Scorciatoie:${RESET}"
  printf "%b\n" "  ${DIM}  stop-all-optional   → ferma: sonarqube, backstage, argocd, airflow, loki, tempo, k8s-dashboard, velero${RESET}"
  printf "%b\n" "  ${DIM}  start-all-optional  → riavviali tutti${RESET}"
  echo ""
}

# ─── stop ─────────────────────────────────────────────────────────────────────
cmd_stop() {
  local alias="$1"
  local info; info=$(_lookup "$alias")
  if [ -z "$info" ]; then
    printf "%b\n" "${RED}Servizio '$alias' non trovato. Usa: ./node-manager.sh list${RESET}"; exit 1
  fi
  read -r ns kind k8sname <<< "$info"
  local cur; cur=$(_get_replicas "$ns" "$kind" "$k8sname")
  if [ "${cur:-0}" -eq 0 ]; then
    printf "%b\n" "${YELLOW}$alias è già fermo${RESET}"; return
  fi
  printf "%b" "${CYAN}Fermo ${BOLD}$alias${RESET}${CYAN} ($ns/$k8sname)... ${RESET}"
  _scale "$ns" "$kind" "$k8sname" 0 > /dev/null
  printf "%b\n" "${GREEN}✓${RESET}"
}

# ─── start ────────────────────────────────────────────────────────────────────
cmd_start() {
  local alias="$1" n="${2:-1}"
  local info; info=$(_lookup "$alias")
  if [ -z "$info" ]; then
    printf "%b\n" "${RED}Servizio '$alias' non trovato. Usa: ./node-manager.sh list${RESET}"; exit 1
  fi
  read -r ns kind k8sname <<< "$info"
  local cur; cur=$(_get_replicas "$ns" "$kind" "$k8sname")
  if [ "${cur:-0}" -ge 1 ]; then
    printf "%b\n" "${YELLOW}$alias è già in esecuzione (replicas=$cur)${RESET}"; return
  fi
  printf "%b" "${CYAN}Avvio ${BOLD}$alias${RESET}${CYAN} ($ns/$k8sname)... ${RESET}"
  _scale "$ns" "$kind" "$k8sname" "$n" > /dev/null
  printf "%b\n" "${GREEN}✓${RESET}"
}

# ─── toggle ───────────────────────────────────────────────────────────────────
cmd_toggle() {
  local alias="$1"
  local info; info=$(_lookup "$alias")
  if [ -z "$info" ]; then
    printf "%b\n" "${RED}Servizio '$alias' non trovato. Usa: ./node-manager.sh list${RESET}"; exit 1
  fi
  read -r ns kind k8sname <<< "$info"
  local cur; cur=$(_get_replicas "$ns" "$kind" "$k8sname")
  if [ "${cur:-0}" -gt 0 ]; then cmd_stop "$alias"; else cmd_start "$alias"; fi
}

# ─── stop/start opzionali ─────────────────────────────────────────────────────
cmd_stop_optional() {
  printf "%b\n" "${BOLD}${YELLOW}Fermo servizi opzionali (non critici)...${RESET}"
  for svc in $OPTIONAL_SERVICES; do cmd_stop "$svc"; done
  echo ""
  printf "%b\n" "${GREEN}✓ Rimangono attivi: kong, postgres, minio, traefik, oauth2-proxy, grafana, prometheus${RESET}"
}

cmd_start_optional() {
  printf "%b\n" "${BOLD}${GREEN}Avvio servizi opzionali...${RESET}"
  for svc in $OPTIONAL_SERVICES; do cmd_start "$svc"; done
  printf "%b\n" "${GREEN}✓ Servizi opzionali avviati${RESET}"
}

# ─── list ─────────────────────────────────────────────────────────────────────
cmd_list() {
  echo ""
  printf "%b\n" "${BOLD}Servizi disponibili:${RESET}"
  printf "  ${BOLD}%-22s %-12s %-12s %-26s %s${RESET}\n" "ALIAS" "NAMESPACE" "KIND" "NOME K8S" "STATO"
  printf "  %s\n" "────────────────────────────────────────────────────────────────────"
  echo "$SERVICE_CATALOG" | awk 'NF==4' | sort -k1,1 | while read -r alias ns kind k8sname; do
    local r; r=$(_get_replicas "$ns" "$kind" "$k8sname")
    local sc sl
    [ "${r:-0}" -gt 0 ] && { sc="$GREEN"; sl="on ($r)"; } || { sc="$RED"; sl="off"; }
    printf "  %-22s %-12s %-12s %-26s ${sc}%s${RESET}\n" "$alias" "$ns" "$kind" "$k8sname" "$sl"
  done
  echo ""
}

# ─── main ─────────────────────────────────────────────────────────────────────
CMD="${1:-status}"
case "$CMD" in
  status|"")          cmd_status ;;
  stop)               [ -z "${2:-}" ] && { echo "Uso: $0 stop <alias>"; exit 1; }; cmd_stop "$2" ;;
  start)              [ -z "${2:-}" ] && { echo "Uso: $0 start <alias>"; exit 1; }; cmd_start "$2" "${3:-1}" ;;
  toggle)             [ -z "${2:-}" ] && { echo "Uso: $0 toggle <alias>"; exit 1; }; cmd_toggle "$2" ;;
  stop-all-optional)  cmd_stop_optional ;;
  start-all-optional) cmd_start_optional ;;
  list)               cmd_list ;;
  *)
    printf "%b\n" "Uso: $0 [status|stop|start|toggle|stop-all-optional|start-all-optional|list] [alias]"
    exit 1 ;;
esac
