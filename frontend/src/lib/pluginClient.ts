// frontend/src/lib/pluginClient.ts
import axios from "axios";

// Prefer env var if you set one in Vite; falls back to localhost
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/* ----------------------------- Types ------------------------------ */
export type PluginInput = Record<string, unknown>;
export type PluginMetadata = Record<string, unknown>;

export interface RunPluginRequest {
  slug: string;
  input?: PluginInput;
  metadata?: PluginMetadata;
  reuse?: boolean;
  instance_id?: string | null;
  mem_limit?: string | null;
  cpu_quota?: number | null;
}

export interface RunPluginSuccess<T = unknown> {
  ok: true;
  slug: string;
  result: T;
}

export interface RunPluginError {
  ok: false;
  error: string;
}

export type RunPluginResponse<T = unknown> =
  | RunPluginSuccess<T>
  | RunPluginError;

/* ----------------------------- Client ----------------------------- */
/**
 * Run a plugin by slug. Use the generic <T> to type the expected result shape.
 * Example: const result = await runPlugin<{ html: string }>("about-us");
 */
export async function runPlugin<T = unknown>(
  slug: string,
  input: PluginInput = {},
  metadata: PluginMetadata = {}
): Promise<T> {
  const payload: RunPluginRequest = { slug, input, metadata };

  const { data } = await axios.post<RunPluginResponse<T>>(
    `${API}/core/plugin/run`,
    payload
  );

  if (!data || (data as RunPluginError).ok === false) {
    const msg =
      (data as RunPluginError)?.error ?? "Plugin run failed (unknown error)";
    throw new Error(msg);
  }

  return (data as RunPluginSuccess<T>).result;
}

/** Stop a running plugin container (optional helper). */
export async function stopPlugin(slug: string, instanceId?: string) {
  const body = { slug, instance_id: instanceId ?? null };
  const { data } = await axios.post<{ ok: boolean; stopped: boolean }>(
    `${API}/core/plugin/stop`,
    body
  );
  return data;
}
