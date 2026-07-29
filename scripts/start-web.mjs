import path from "node:path";

import { startProdServer } from "vinext/server/prod-server";

const rawPort = process.env.PORT ?? "3000";
if (!/^[0-9]+$/.test(rawPort)) {
  throw new Error(`Invalid PORT: ${rawPort}`);
}

const port = Number(rawPort);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error(`Invalid PORT: ${rawPort}`);
}

const host = process.env.UAI_FORGE_WEB_HOST || "0.0.0.0";

await startProdServer({
  host,
  port,
  outDir: path.resolve(process.cwd(), "dist"),
});
