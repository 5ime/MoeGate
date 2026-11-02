# MoeGate 流量取证 sidecar 镜像
#
# 该镜像只做一件事：在目标容器的网络命名空间里跑 tcpdump 把流量写成 pcap。
# 构建：
#   docker build -t moegate-tap:latest deploy/tap
# 或直接启动 MoeGate（镜像缺失时会用本目录自动构建一次）。
#
# 为什么用 alpine：镜像 < 30MB，抓包进程几乎不占资源，不影响靶机性能。
FROM alpine:3.20

RUN apk add --no-cache tcpdump tini \
    && mkdir -p /capture

# tini 负责回收僵尸进程，便于 docker stop 时让 tcpdump 正常退出并 flush pcap
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["tcpdump", "-i", "any", "-n", "-U", "-w", "/capture/traffic.pcap"]
