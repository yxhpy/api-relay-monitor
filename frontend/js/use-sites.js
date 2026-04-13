/**
 * Composable: Sites 模块
 * 职责：中转站列表 CRUD、筛选、分页、详情
 */
function useSites(api, loading) {
  const sitesData = Vue.ref([]);
  const sitesTotal = Vue.ref(0);
  const sitesFilters = Vue.reactive({ keyword: '', type: '', status: '', risk_level: '', min_score: 0 });
  const sitesPagination = Vue.reactive({ page: 1, page_size: 10 });
  const sitesSort = Vue.reactive({ sort_by: 'overall_score', sort_order: 'desc' });

  const siteDialogVisible = Vue.ref(false);
  const editingSite = Vue.ref(null);
  const siteForm = Vue.reactive({
    name: '', url: '', api_url: '', relay_type: '官转', status: 'active',
    price_multiplier: 1, pricing_info: '', supported_models_str: '', risk_level: 'low', risk_notes: '',
  });

  const siteDetailVisible = Vue.ref(false);
  const siteDetail = Vue.ref(null);
  const scoreItems = [
    { key: 'overall_score', label: '综合评分' },
    { key: 'stability_score', label: '稳定性' },
    { key: 'price_score', label: '价格' },
    { key: 'community_rating', label: '社区评价' },
    { key: 'update_speed_score', label: '更新速度' },
  ];

  async function loadSites() {
    loading.sites = true;
    try {
      const params = new URLSearchParams({
        page: sitesPagination.page,
        page_size: sitesPagination.page_size,
        sort_by: sitesSort.sort_by,
        sort_order: sitesSort.sort_order,
      });
      if (sitesFilters.type) params.set('type', sitesFilters.type);
      if (sitesFilters.status) params.set('status', sitesFilters.status);
      if (sitesFilters.risk_level) params.set('risk_level', sitesFilters.risk_level);
      if (sitesFilters.min_score > 0) params.set('min_score', sitesFilters.min_score);
      if (sitesFilters.keyword) params.set('keyword', sitesFilters.keyword);
      const data = await api.get('/api/sites?' + params.toString());
      sitesData.value = data.items || data || [];
      sitesTotal.value = data.total || sitesData.value.length;
    } catch (e) {
      ElementPlus.ElMessage.error('加载站点列表失败: ' + e.message);
    } finally {
      loading.sites = false;
    }
  }

  function handleSitesSortChange({ prop, order }) {
    if (prop) {
      sitesSort.sort_by = prop;
      sitesSort.sort_order = order === 'ascending' ? 'asc' : 'desc';
    }
    loadSites();
  }

  function openSiteDialog(site) {
    editingSite.value = site;
    if (site) {
      Object.assign(siteForm, {
        name: site.name || '', url: site.url || '', api_url: site.api_url || '',
        relay_type: site.relay_type || '官转', status: site.status || 'active',
        price_multiplier: site.price_multiplier || 1, pricing_info: site.pricing_info || '',
        supported_models_str: (site.supported_models || []).join(', '),
        risk_level: site.risk_level || 'low', risk_notes: site.risk_notes || '',
      });
    } else {
      Object.assign(siteForm, {
        name: '', url: '', api_url: '', relay_type: '官转', status: 'active',
        price_multiplier: 1, pricing_info: '', supported_models_str: '', risk_level: 'low', risk_notes: '',
      });
    }
    siteDialogVisible.value = true;
  }

  async function saveSite() {
    if (!siteForm.name || !siteForm.url) {
      ElementPlus.ElMessage.warning('请填写必填字段');
      return;
    }
    loading.siteSave = true;
    try {
      const payload = { ...siteForm };
      payload.supported_models = payload.supported_models_str ? payload.supported_models_str.split(',').map(s => s.trim()).filter(Boolean) : [];
      delete payload.supported_models_str;
      if (editingSite.value) {
        await api.put('/api/sites/' + editingSite.value.id, payload);
        ElementPlus.ElMessage.success('站点更新成功');
      } else {
        await api.post('/api/sites', payload);
        ElementPlus.ElMessage.success('站点添加成功');
      }
      siteDialogVisible.value = false;
      loadSites();
    } catch (e) {
      ElementPlus.ElMessage.error('保存失败: ' + e.message);
    } finally {
      loading.siteSave = false;
    }
  }

  async function deleteSite(id) {
    try {
      await api.del('/api/sites/' + id);
      ElementPlus.ElMessage.success('删除成功');
      loadSites();
    } catch (e) {
      ElementPlus.ElMessage.error('删除失败: ' + e.message);
    }
  }

  async function viewSiteDetail(id) {
    try {
      siteDetail.value = await api.get('/api/sites/' + id);
      siteDetailVisible.value = true;
    } catch (e) {
      ElementPlus.ElMessage.error('加载详情失败: ' + e.message);
    }
  }

  return {
    sitesData, sitesTotal, sitesFilters, sitesPagination, sitesSort,
    siteDialogVisible, editingSite, siteForm,
    siteDetailVisible, siteDetail, scoreItems,
    loadSites, handleSitesSortChange, openSiteDialog, saveSite, deleteSite, viewSiteDetail,
  };
}
