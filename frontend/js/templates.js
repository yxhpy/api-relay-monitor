/**
 * 模板加载器 — 在 Vue app mount 前通过 fetch 加载所有模板片段，注入到 #app 中
 * 设计模式：异步模板注入 (Async Template Injection)
 */
(function () {
  'use strict';

  const TEMPLATES_BASE = '/static/templates/';

  // 需要加载的模板列表（按注入顺序）
  const TEMPLATE_FILES = [
    'dashboard.html',
    'sites.html',
    'crawl.html',
    'analysis.html',
    'settings.html',
    'dialogs.html',
  ];

  /**
   * 加载所有模板片段并注入到 #app 的 content-area 中
   * @returns {Promise<void>}
   */
  async function loadTemplates() {
    // 找到模板注入的目标容器：content-area 内的 transition > div
    const contentDiv = document.getElementById('templates-inject-point');
    if (!contentDiv) {
      console.error('[templates.js] #templates-inject-point not found');
      return;
    }

    // 并发加载所有模板
    const results = await Promise.all(
      TEMPLATE_FILES.map(async (file) => {
        try {
          const resp = await fetch(TEMPLATES_BASE + file);
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
          return await resp.text();
        } catch (err) {
          console.error(`[templates.js] Failed to load template: ${file}`, err);
          return '';
        }
      })
    );

    // 按顺序拼接并注入
    contentDiv.innerHTML = results.join('\n');
  }

  // 暴露到全局
  window.loadTemplates = loadTemplates;
})();
