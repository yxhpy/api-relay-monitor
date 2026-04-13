/**
 * 用户评价模块
 */
(function () {
  'use strict';

  const reviewFilters = Vue.reactive({
    site_id: null,
    platform: null,
    sentiment: null,
    keyword: '',
  });
  const reviewList = Vue.ref([]);
  const reviewStats = Vue.ref({});
  const reviewSites = Vue.ref([]);
  const reviewPagination = Vue.reactive({ page: 1, total: 0, total_pages: 0 });
  const reviewSeeding = Vue.ref(false);
  const reviewAnalyzing = Vue.ref(false);
  const drilldownSiteId = Vue.ref(null);
  const drilldownData = Vue.ref({});
  const analysisResult = Vue.ref({});

  async function loadReviewSites() {
    try {
      const data = await api.get('/sites', { page_size: 100 });
      reviewSites.value = data.items || [];
    } catch (e) { console.error('loadReviewSites:', e); }
  }

  async function loadReviews(page) {
    if (page) reviewPagination.page = page;
    try {
      const params = { page: reviewPagination.page, page_size: 20 };
      if (reviewFilters.site_id) params.site_id = reviewFilters.site_id;
      if (reviewFilters.platform) params.platform = reviewFilters.platform;
      if (reviewFilters.sentiment) params.sentiment = reviewFilters.sentiment;
      if (reviewFilters.keyword) params.keyword = reviewFilters.keyword;
      const data = await api.get('/reviews', params);
      reviewList.value = data.items || [];
      reviewPagination.total = data.total || 0;
      reviewPagination.total_pages = data.total_pages || 0;
    } catch (e) { console.error('loadReviews:', e); }
  }

  async function loadReviewStats() {
    try {
      const params = {};
      if (reviewFilters.site_id) params.site_id = reviewFilters.site_id;
      if (reviewFilters.platform) params.platform = reviewFilters.platform;
      reviewStats.value = await api.get('/reviews/stats', params);
    } catch (e) { console.error('loadReviewStats:', e); }
  }

  async function seedReviews() {
    reviewSeeding.value = true;
    try {
      const seeds = [
        { relay_site_id: 7, platform: "linux_do", sentiment: "positive", content: "模型又多又稳定，就是价格不美丽……只能说是最稳的渠道了", likes: 45 },
        { relay_site_id: 7, platform: "linux_do", sentiment: "negative", content: "风控国内支付渠道，大陆/香港信用卡充值就会触发封禁", likes: 23 },
        { relay_site_id: 2, platform: "linux_do", sentiment: "positive", content: "模型挺全的，注册即送2000万Tokens", likes: 38 },
        { relay_site_id: 2, platform: "linux_do", sentiment: "negative", content: "高峰期不到10 tokens/s，经常超时", likes: 31 },
        { relay_site_id: 2, platform: "x", sentiment: "mixed", content: "以前接近80 tokens/s，现在用的人太多降速了", likes: 12 },
        { relay_site_id: 3, platform: "linux_do", sentiment: "negative", content: "o1全是不思考的，降智有点离谱", likes: 67 },
        { relay_site_id: 3, platform: "linux_do", sentiment: "negative", content: "判断是否是中国作息来封禁账号，API里还有余额", likes: 55 },
        { relay_site_id: 3, platform: "linux_do", sentiment: "positive", content: "很稳定，能开票，企业级", likes: 15 },
        { relay_site_id: 1, platform: "v2ex", sentiment: "positive", content: "比市面上中转站的价格都低而且支持高并发", likes: 28 },
        { relay_site_id: 1, platform: "v2ex", sentiment: "negative", content: "响应速度慢，调用Claude/Gemini非常慢", likes: 19 },
        { relay_site_id: 6, platform: "v2ex", sentiment: "negative", content: "21块钱做了几次嵌入就没了？计费太狠", likes: 42 },
        { relay_site_id: 6, platform: "v2ex", sentiment: "positive", content: "老牌站，国内可用", likes: 8 },
      ];
      let created = 0;
      for (const s of seeds) {
        try {
          const r = await fetch('/api/reviews', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(s),
          });
          if (r.ok) created++;
        } catch (e) {}
      }
      ElMessage.success(`成功导入 ${created} 条种子评价`);
      loadReviews();
      loadReviewStats();
    } catch (e) {
      ElMessage.error('导入失败: ' + e.message);
    } finally {
      reviewSeeding.value = false;
    }
  }

  async function runAnalysis() {
    reviewAnalyzing.value = true;
    try {
      const body = { limit: 50 };
      if (reviewFilters.site_id) body.site_id = reviewFilters.site_id;
      if (reviewFilters.platform) body.platform = reviewFilters.platform;
      const r = await fetch('/api/reviews/analyze', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      analysisResult.value = await r.json();
      ElMessage.success('LLM 分析完成');
    } catch (e) {
      ElMessage.error('分析失败: ' + e.message);
    } finally {
      reviewAnalyzing.value = false;
    }
  }

  async function loadDrilldown() {
    if (!drilldownSiteId.value) { drilldownData.value = {}; return; }
    try {
      drilldownData.value = await api.get(`/reviews/site/${drilldownSiteId.value}/drilldown`);
    } catch (e) { console.error('loadDrilldown:', e); }
  }

  function sentimentTagType(s) {
    return { positive: 'success', negative: 'danger', neutral: '', mixed: 'warning' }[s] || '';
  }
  function sentimentLabel(s) {
    return { positive: '👍 正面', negative: '👎 负面', neutral: '😐 中性', mixed: '🤔 混合' }[s] || s;
  }

  // 在首次切换到 reviews 页面时加载数据
  function initReviews() {
    loadReviewSites();
    loadReviews();
    loadReviewStats();
  }

  // 暴露到全局
  window.useReviews = {
    reviewFilters, reviewList, reviewStats, reviewSites, reviewPagination,
    reviewSeeding, reviewAnalyzing, drilldownSiteId, drilldownData, analysisResult,
    loadReviews, loadReviewStats, loadReviewSites, seedReviews, runAnalysis, loadDrilldown,
    sentimentTagType, sentimentLabel, initReviews,
  };
})();
