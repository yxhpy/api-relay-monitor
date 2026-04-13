/**
 * Composable: Analysis 模块
 * 职责：分析报告、站点评估
 */
function useAnalysis(api, loading) {
  const reports = Vue.ref([]);
  const analysisFilter = Vue.ref('all');
  const selectedReport = Vue.ref(null);
  const evaluateUrl = Vue.ref('');
  const evaluateResult = Vue.ref(null);

  async function loadReports() {
    loading.reports = true;
    try {
      const params = new URLSearchParams();
      if (analysisFilter.value && analysisFilter.value !== 'all') params.set('report_type', analysisFilter.value);
      const data = await api.get('/api/analysis/reports?' + params.toString());
      reports.value = data.items || data || [];
      if (reports.value.length > 0 && (!selectedReport.value || !reports.value.find(r => r.id === selectedReport.value.id))) {
        selectedReport.value = reports.value[0];
      }
    } catch (e) {
      ElementPlus.ElMessage.error('加载报告失败: ' + e.message);
    } finally {
      loading.reports = false;
    }
  }

  function selectReport(report) { selectedReport.value = report; }

  async function runAnalysis() {
    loading.analysisRun = true;
    try {
      await api.post('/api/analysis/run', {});
      ElementPlus.ElMessage.success('分析任务已启动');
      loadReports();
    } catch (e) {
      ElementPlus.ElMessage.error('运行分析失败: ' + e.message);
    } finally {
      loading.analysisRun = false;
    }
  }

  async function evaluateSite() {
    if (!evaluateUrl.value) { ElementPlus.ElMessage.warning('请输入站点 ID 或 URL'); return; }
    loading.evaluate = true;
    evaluateResult.value = null;
    try {
      let siteId = parseInt(evaluateUrl.value);
      if (isNaN(siteId)) {
        const sites = await api.get(`/api/sites?search=${encodeURIComponent(evaluateUrl.value)}`);
        if (sites && sites.length > 0) {
          siteId = sites[0].id;
        } else {
          ElementPlus.ElMessage.error('未找到匹配的站点，请确认 URL 或直接输入站点 ID');
          return;
        }
      }
      evaluateResult.value = await api.post('/api/analysis/evaluate-site', { site_id: siteId });
    } catch (e) {
      ElementPlus.ElMessage.error('评估失败: ' + e.message);
    } finally {
      loading.evaluate = false;
    }
  }

  return {
    reports, analysisFilter, selectedReport, evaluateUrl, evaluateResult,
    loadReports, selectReport, runAnalysis, evaluateSite,
  };
}
