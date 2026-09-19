"""Local/dev entry point: `python run.py` starts the API on port 4000.

Override with env vars, e.g. PORT=5000. Behind a reverse proxy or load
balancer, set FORWARDED_ALLOW_IPS to the proxy's address (or "*" if it is
the only thing that can reach this server) so rate limiting sees each
user's real IP instead of the proxy's.
"""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", "4000")),
        reload=True,
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )
