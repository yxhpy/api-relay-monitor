/**
 * Composable: Dashboard 模块
 * 职责：仪表盘数据加载和状态管理
 */
function useDashboard(api, loading, Formatters) {
  const dashboardStats = Vue.ref({});
  const topPicks = Vue.ref([]);
  const riskAlerts = Vue.ref([]);
  const recentActivity = Vue.ref([]);
  const unreadAlerts = Vue.ref(0);

  async function loadDashboard() {
    loading.dashboard = true;
    try {
      const [stats, picks, alerts] = await Promise.allSettled([
        api.get('/api/dashboard/stats'),
        api.get('/api/dashboard/top-picks'),
        api.get('/api/dashboard/risk-alerts'),
      ]);
      if (stats.status === 'fulfilled') dashboardStats.value = stats.value || {};
      if (picks.status === 'fulfilled') topPicks.value = picks.value || [];
      if (alerts.status === 'fulfilled') {
        riskAlerts.value = alerts.value || [];
        unreadAlerts.value = riskAlerts.value.filter(a => !a.read).length;
      }
      const activities = [];
      topPicks.value.slice(0, 3).forEach(p => {
        activities.push({
          id: 'p-' + p.id,
          message: `推荐站点: ${p.name} (评分: ${p.overall_score?.toFixed(1)})`,
          color: '#67c23a',
          time: Formatters.formatTime(p.updated_at || p.created_at)
        });
      });
      riskAlerts.value.slice(0, 3).forEach(a => {
        activities.push({
          id: 'a-' + a.id,
          message: a.title || a.name || '风险预警',
          color: '#f56c6c',
          time: Formatters.formatTime(a.time || a.created_at)
        });
      });
      recentActivity.value = activities;
    } catch (e) {
      ElementPlus.ElMessage.error('加载仪表盘失败: ' + e.message);
    } finally {
      loading.dashboard = false;
    }
  }

  return { dashboardStats, topPicks, riskAlerts, recentActivity, unreadAlerts, loadDashboard };
}
