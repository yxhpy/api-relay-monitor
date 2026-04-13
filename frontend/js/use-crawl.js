/**
 * Composable: Crawl 模块
 * 职责：采集中心数据加载、触发采集、详情查看
 */
function useCrawl(api, loading, Formatters) {
  const crawlResults = Vue.ref([]);
  const crawlTotal = Vue.ref(0);
  const crawlFilters = Vue.reactive({ source: 'all' });
  const crawlPagination = Vue.reactive({ page: 1, page_size: 10 });
  const crawlTriggerSource = Vue.ref('all');
  const crawlDetailVisible = Vue.ref(false);
  const crawlDetail = Vue.ref(null);

  async function loadCrawlResults() {
    loading.crawl = true;
    try {
      const params = new URLSearchParams({
        page: crawlPagination.page,
        page_size: crawlPagination.page_size,
      });
      if (crawlFilters.source && crawlFilters.source !== 'all') params.set('source', crawlFilters.source);
      const data = await api.get('/api/crawl/results?' + params.toString());
      crawlResults.value = data.items || data || [];
      crawlTotal.value = data.total || crawlResults.value.length;
    } catch (e) {
      ElementPlus.ElMessage.error('加载采集结果失败: ' + e.message);
    } finally {
      loading.crawl = false;
    }
  }

  async function triggerCrawl(source) {
    loading.crawlTrigger = true;
    try {
      await api.post('/api/crawl/trigger', { source: source || 'all' });
      ElementPlus.ElMessage.success('采集任务已触发');
    } catch (e) {
      ElementPlus.ElMessage.error('触发采集失败: ' + e.message);
    } finally {
      loading.crawlTrigger = false;
    }
  }

  function viewCrawlDetail(row) {
    crawlDetail.value = row;
    crawlDetailVisible.value = true;
  }

  async function markProcessed(row) {
    try {
      await api.put('/api/crawl/results/' + row.id, { processed: true });
      row.processed = true;
      ElementPlus.ElMessage.success('已标记为已处理');
    } catch (e) {
      ElementPlus.ElMessage.error('操作失败: ' + e.message);
    }
  }

  return {
    crawlResults, crawlTotal, crawlFilters, crawlPagination,
    crawlTriggerSource, crawlDetailVisible, crawlDetail,
    loadCrawlResults, triggerCrawl, viewCrawlDetail, markProcessed,
  };
}
