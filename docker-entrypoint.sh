#!/bin/sh
set -e

# 启动时读取挂载的 docker.sock 组 GID，自动加入 moegate 用户，避免手动配置 DOCKER_GID
if [ "$(id -u)" = "0" ] && [ -S /var/run/docker.sock ]; then
  sock_gid="$(stat -c '%g' /var/run/docker.sock)"
  if [ -n "$sock_gid" ]; then
    group_name="$(getent group "$sock_gid" | cut -d: -f1 || true)"
    if [ -z "$group_name" ]; then
      group_name=dockersock
      if ! groupadd -g "$sock_gid" "$group_name" 2>/dev/null; then
        group_name="$(getent group "$sock_gid" | cut -d: -f1 || true)"
      fi
    fi
    if [ -n "$group_name" ]; then
      usermod -aG "$group_name" moegate 2>/dev/null || true
    fi
  fi
fi

if [ "$(id -u)" = "0" ]; then
  exec gosu moegate "$@"
fi

exec "$@"
