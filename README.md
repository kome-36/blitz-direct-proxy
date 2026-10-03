# blitz-direct-proxy

Direct (no argo tunnel) VLESS+WS+TLS proxy node, adapted for blitz.cloud:
the platform edge terminates TLS for `*.blitz.cloud` and forwards plain HTTP
to the container's single `$PORT`; xray dispatches by path (`/vless`).

Builds automatically via GitHub Actions -> `ghcr.io/<owner>/blitz-direct-proxy:latest`.

## Deploy on blitz.cloud

1. Host something new -> "An app that is already packaged up",
   image `ghcr.io/<owner>/blitz-direct-proxy:latest`, app name `proxy`.
2. After deploy, app -> Settings -> Environment, set and restart:
   - `UUID` = your node UUID (generate one; keep it secret-ish, it is the password)
   - `DOMAIN` = `proxy.cloud.blitz.cloud`
3. Subscription: `https://proxy.cloud.blitz.cloud/sub`
