/**
 * Cloudflare Worker — API Gateway for FotoFindr
 *
 * Routes all /api/* requests to the DigitalOcean backend.
 * Handles CORS preflight and basic rate limiting headers.
 *
 * Deploy: wrangler deploy
 */

const BACKEND_URL = "https://your-droplet-ip-or-domain.com"; // TODO: set in wrangler.toml

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

export default {
  async fetch(request, env) {
    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url = new URL(request.url);

    // Strip /api prefix and forward to backend
    const backendPath = url.pathname.replace(/^\/api/, "");
    const backendUrl = `${env.BACKEND_URL || BACKEND_URL}${backendPath}${url.search}`;

    const proxiedRequest = new Request(backendUrl, {
      method: request.method,
      headers: request.headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
    });

    try {
      const response = await fetch(proxiedRequest);
      const newHeaders = new Headers(response.headers);
      Object.entries(CORS_HEADERS).forEach(([k, v]) => newHeaders.set(k, v));
      return new Response(response.body, {
        status: response.status,
        headers: newHeaders,
      });
    } catch (err) {
      return new Response(JSON.stringify({ error: "Gateway error", detail: String(err) }), {
        status: 502,
        headers: { "Content-Type": "application/json", ...CORS_HEADERS },
      });
    }
  },
};
