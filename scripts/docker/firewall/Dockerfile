FROM alpine:3.20

RUN apk add --no-cache \
    iptables \
    iproute2 \
    tcpdump \
    bash

COPY firewall.sh /usr/local/bin/firewall.sh

RUN chmod +x /usr/local/bin/firewall.sh

ENTRYPOINT ["/usr/local/bin/firewall.sh"]
