# MatchPulse Production Deployment

## Nginx

Canonical production config:

    deploy/nginx/matchpulse.conf

Install/update:

    sudo cp deploy/nginx/matchpulse.conf /etc/nginx/sites-available/matchpulse
    sudo nginx -t
    sudo systemctl reload nginx

The exact `/competitions` location is intentional. Without it, the SPA `try_files`
rule can redirect `/competitions` to `/competitions/`, causing a redirect loop
behind the production proxy/CDN.

## Frontend

Build from:

    backend/frontend

Command:

    npm ci
    npm run build

The build script fixes `dist` permissions so nginx can read the generated files
even when the deployment user's umask is restrictive.
