/**
 * App 主入口 — 组合各模块，创建并挂载 Vue 应用
 * 设计模式：组合模式 (Composition Pattern) + 服务层模式
 */
(function () {
  'use strict';

  const { createApp, ref, reactive, computed, onMounted, onUnmounted, watch } = Vue;

  const loading = reactive({
    dashboard: false, sites: false, crawl: false, crawlTrigger: false,
    reports: false, analysisRun: false, evaluate: false, settings: false, siteSave: false,
  });

  const app = createApp({
    setup() {
      // --- 组合各模块 ---
      const dashboard = useDashboard(api, loading, Formatters);
      const sites = useSites(api, loading);
      const crawl = useCrawl(api, loading, Formatters);
      const analysis = useAnalysis(api, loading);
      const settingsModule = useSettings(api, loading);
      const reviews = useReviews;

      // --- 全局 UI 状态 ---
      const initializing = ref(true);
      const sidebarCollapsed = ref(false);
      const currentPage = ref('dashboard');

      const navItems = [
        { key: 'dashboard', label: '仪表盘', icon: 'Odometer' },
        { key: 'sites', label: '中转站列表', icon: 'Monitor' },
        { key: 'reviews', label: '用户评价', icon: 'ChatDotRound' },
        { key: 'crawl', label: '采集中心', icon: 'Download' },
        { key: 'analysis', label: '智能分析', icon: 'DataAnalysis' },
        { key: 'settings', label: '系统设置', icon: 'Setting' },
      ];

      const currentNavLabel = computed(() => {
        const item = navItems.find(n => n.key === currentPage.value);
        return item ? item.label : '';
      });

      const Refresh = ElementPlusIconsVue.Refresh;
      const Bell = ElementPlusIconsVue.Bell;
      const Setting = ElementPlusIconsVue.Setting;
      const Search = ElementPlusIconsVue.Search;

      // --- 路由 ---
      function navigateTo(page) {
        currentPage.value = page;
        window.location.hash = page;
      }

      function handleHash() {
        const hash = window.location.hash.replace('#', '');
        if (hash && navItems.find(n => n.key === hash)) currentPage.value = hash;
      }

      function refreshCurrentPage() {
        if (currentPage.value === 'dashboard') dashboard.loadDashboard();
        else if (currentPage.value === 'sites') sites.loadSites();
        else if (currentPage.value === 'crawl') { crawl.loadCrawlSources(); crawl.loadCrawlResults(); }
        else if (currentPage.value === 'analysis') analysis.loadReports();
        else if (currentPage.value === 'reviews') { reviews.initReviews(); }
      }

      // --- 生命周期 ---
      let refreshTimer = null;

      onMounted(async () => {
        settingsModule.loadSettings();
        handleHash();
        window.addEventListener('hashchange', handleHash);
        await dashboard.loadDashboard();
        initializing.value = false;
        refreshTimer = setInterval(() => {
          if (currentPage.value === 'dashboard') dashboard.loadDashboard();
        }, 60000);
      });

      onUnmounted(() => {
        window.removeEventListener('hashchange', handleHash);
        if (refreshTimer) clearInterval(refreshTimer);
      });

      watch(currentPage, (page) => {
        if (page === 'dashboard') dashboard.loadDashboard();
        else if (page === 'sites') sites.loadSites();
        else if (page === 'crawl') { crawl.loadCrawlSources(); crawl.loadCrawlResults(); }
        else if (page === 'analysis') analysis.loadReports();
        else if (page === 'reviews') { reviews.initReviews(); }
      });

      return {
        initializing, sidebarCollapsed, currentPage, loading, navItems, currentNavLabel,
        Refresh, Bell, Setting, Search,
        // Dashboard
        ...dashboard,
        // Sites
        ...sites,
        // Crawl
        ...crawl,
        // Analysis
        ...analysis,
        // Settings
        ...settingsModule,
        // Reviews
        ...reviews,
        // Navigation
        navigateTo, refreshCurrentPage,
        // Formatters
        ...Formatters,
      };
    },
  });

  app.use(ElementPlus);
  for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component);
    // DOM 模板中浏览器会把标签自动全小写，同时注册小写别名
    app.component(key.toLowerCase(), component);
  }
  app.mount('#app');
})();
