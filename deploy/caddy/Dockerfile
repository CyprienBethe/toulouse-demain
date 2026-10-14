# Caddy with the rate limiting module, which is not in the official image.
# Both versions are pinned: Caddy 2.11.7 (official image tags) and the module
# commit 5625512f24f6f59d6f64fb3aafe5eecff0b286db (2026-06-12).
FROM caddy:2.11.7-builder AS builder
RUN xcaddy build --with github.com/mholt/caddy-ratelimit@5625512f24f6f59d6f64fb3aafe5eecff0b286db

FROM caddy:2.11.7
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
