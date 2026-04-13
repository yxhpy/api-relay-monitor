/**
 * API 服务层 — 封装所有后端通信
 * 职责单一：只负责 HTTP 请求和错误处理
 */
const API_BASE = '';

class ApiService {
  constructor(baseURL = '', timeout = 30000) {
    this.baseURL = baseURL;
    this.timeout = timeout;
  }

  async request(path, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);
    try {
      const { signal: _s, ...restOptions } = options;
      const resp = await fetch(this.baseURL + path, {
        headers: { 'Content-Type': 'application/json', ...restOptions.headers },
        signal: controller.signal,
        ...restOptions,
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || err.message || `HTTP ${resp.status}`);
      }
      if (resp.status === 204) return null;
      return await resp.json();
    } catch (e) {
      if (e.name === 'AbortError') {
        console.error(`API Timeout [${path}]: request exceeded ${this.timeout / 1000}s`);
        throw new Error('请求超时，请稍后重试');
      }
      console.error(`API Error [${path}]:`, e);
      throw e;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  get(path) { return this.request(path); }
  post(path, body) { return this.request(path, { method: 'POST', body: JSON.stringify(body) }); }
  put(path, body) { return this.request(path, { method: 'PUT', body: JSON.stringify(body) }); }
  del(path) { return this.request(path, { method: 'DELETE' }); }
}

const api = new ApiService(API_BASE);
