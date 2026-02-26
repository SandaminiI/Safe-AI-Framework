import axios from "axios";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8012";

export type PluginStartReq = {
  slug: string;
  reuse?: boolean;
  instance_id?: string | null;
  mem_limit?: string;
};

export type PluginStartRes = {
  ok: boolean;
  slug: string;
  host_port: string;
  base_url: string;
};

export type PluginRunReq = {
  slug: string;
  input?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  reuse?: boolean;
  instance_id?: string | null;
  mem_limit?: string;
};

export type PluginRunRes = {
  ok: boolean;
  slug: string;
  result: unknown;
};

export type PluginStopReq = {
  slug: string;
  instance_id?: string | null;
};

export type PluginStopRes = {
  ok: boolean;
  stopped: boolean;
};

export async function startPlugin(payload: PluginStartReq): Promise<PluginStartRes> {
  const { data } = await axios.post<PluginStartRes>(`${BASE}/core/plugins/start`, payload);
  return data;
}

export async function runPlugin(payload: PluginRunReq): Promise<PluginRunRes> {
  const { data } = await axios.post<PluginRunRes>(`${BASE}/core/plugins/run`, payload);
  return data;
}

export async function stopPlugin(payload: PluginStopReq): Promise<PluginStopRes> {
  const { data } = await axios.post<PluginStopRes>(`${BASE}/core/plugins/stop`, payload);
  return data;
}
