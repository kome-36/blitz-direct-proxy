# blitz-direct-proxy

Direct (no argo tunnel) VLESS+WS+TLS proxy node, adapted for blitz.cloud:
the platform edge terminates TLS for `*.blitz.cloud` and forwards plain HTTP
to the container's single `$PORT`; xray dispatches by path (`/vless`).

Builds automatically via GitHub Actions -> `ghcr.io/<owner>/blitz-direct-proxy:latest`.


