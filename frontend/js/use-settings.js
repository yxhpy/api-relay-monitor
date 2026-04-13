/**
 * Composable: Settings 模块
 * 职责：系统设置加载/保存
 */
function useSettings(api, loading) {
  const settings = Vue.reactive({
    llm_api_key: '', llm_api_base: 'https://api.openai.com/v1', llm_model: 'gpt-4o-mini',
    telegram_bot_token: '', telegram_chat_id: '',
    crawl_interval: 60, enabled_sources: ['linux_do', 'v2ex', 'github', 'rss'],
  });

  async function loadSettings() {
    const saved = localStorage.getItem('api_relay_monitor_settings');
    if (saved) {
      try { Object.assign(settings, JSON.parse(saved)); } catch (e) {}
    }
    try {
      const backendConfig = await api.get('/api/config');
      if (backendConfig && typeof backendConfig === 'object') {
        Object.assign(settings, backendConfig);
      }
    } catch (e) { /* backend config endpoint may not exist */ }
  }

  async function saveSettings() {
    loading.settings = true;
    try {
      localStorage.setItem('api_relay_monitor_settings', JSON.stringify(settings));
      try { await api.post('/api/config', settings); } catch (e) { /* backend may not support */ }
      ElementPlus.ElMessage.success('设置已保存到本地浏览器。后端配置需通过 .env 文件修改并重启服务才能生效。');
    } finally {
      loading.settings = false;
    }
  }

  return { settings, loadSettings, saveSettings };
}
