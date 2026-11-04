# AsOfRAG web

Temporal reliability control room for financial RAG. Built with React,
TypeScript, Vite, and the TrueForge UI/SDK.

```bash
npm install
npm run dev
npm run lint
npm run build
```

The browser uses same-origin routes:

- `/api/*` for the AsOfRAG backend
- `/trueforge/*` for the embedded TrueForge harness

When the API is unavailable, the control room switches to a clearly marked,
deterministic **Demo Preview**. The TrueForge dock remains embedded and reports
its own connection state.

## Container

```bash
docker build -t asofrag-web .
docker run --rm -p 8080:80 asofrag-web
```

The Nginx image expects an `mcp-server` host on port `8000` and a TrueForge
harness available through `host.docker.internal:8791`.
