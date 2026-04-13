/**
 * 格式化工具集
 */
const Formatters = {
  scoreColor(score) {
    if (!score) return '#909399';
    if (score >= 8) return '#67c23a';
    if (score >= 7) return '#85ce61';
    if (score >= 5) return '#e6a23c';
    return '#f56c6c';
  },
  riskTagType(level) {
    return level === 'high' ? 'danger' : level === 'medium' ? 'warning' : 'success';
  },
  riskLabel(level) {
    const map = { high: '高风险', medium: '中风险', low: '低风险' };
    return map[level] || level || '-';
  },
  statusTagType(s) {
    return s === 'active' ? 'success' : s === 'suspended' ? 'danger' : 'info';
  },
  statusLabel(s) {
    const map = { active: '活跃', suspended: '已暂停', unknown: '未知' };
    return map[s] || s || '-';
  },
  sourceLabel(s) {
    const map = {
      linux_do: 'linux.do',
      linux_do_tag: 'linux.do',
      v2ex: 'V2EX',
      github: 'GitHub',
      github_discussions: 'GitHub',
      github_awesome: 'GitHub',
      hackernews: 'HackerNews',
      known_sites: '白名单种子',
      nav_sites: '导航站',
      reddit: 'Reddit',
      nitter: 'X/Twitter',
      zhihu: '知乎',
      producthunt: 'ProductHunt',
      weibo: '微博',
      douyin: '抖音热榜',
      rss_feed: 'RSS',
      rss: 'RSS',
    };
    return map[s] || s;
  },
  formatTime(t) {
    if (!t) return '-';
    try {
      const d = new Date(t);
      if (isNaN(d.getTime())) return t;
      return d.toLocaleString('zh-CN', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
      });
    } catch { return t; }
  },
  sanitizeHtml(html) {
    return html
      .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
      .replace(/\bon\w+\s*=\s*["'][^"']*["']/gi, '')
      .replace(/\bon\w+\s*=\s*[^\s>]*/gi, '')
      .replace(/href\s*=\s*["']javascript:/gi, 'href="#"');
  },
  renderMarkdown(text) {
    if (!text) return '';
    const md = window.markdownit({ html: false, linkify: true, breaks: true });
    return this.sanitizeHtml(md.render(text));
  }
};
