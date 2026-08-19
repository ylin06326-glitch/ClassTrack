/* ============================================================
   ClassTrack v1.2 - 前端应用逻辑
   优化: 即时UI更新 / 学号显示 / iOS级流畅体验
   ============================================================ */

// ============================================================
// 全局状态
// ============================================================
const State = {
  currentClassId: 1,
  classes: [],
  students: [],
  groups: [],
  unassigned: [],
  homeworkCache: {},
  activeTab: "grouping",
  selectedCount: 6,
  isLocked: false,
  selectedStudents: new Set(),
  importMode: "excel",
  hwSubtab: "manual",  // 作业登记子Tab: manual / pcscan / mobile
  displayMode: 'name',  // 姓名显示模式: 'name' | 'code' | 'auto'（auto=已完成显名/未完成显学号）
  // 成绩管理
  examCache: {},        // key: "examName_date" → {student_id: {score, ...}}
  currentExamName: '',
  currentExamDate: '',
  examList: [],         // [{exam_name, date, total_score}]
  // 作业种类
  homeworkTypes: [],
  currentHomeworkTypeId: 1,
};

/** 生成作业缓存key（包含作业种类ID，支持同一天多种作业独立缓存） */
function cacheKey(date, hwTypeId) {
  return `${date}_${hwTypeId || 0}`;
}

// ============================================================
// 性能优化：防抖/节流
// ============================================================
function debounce(fn, delay) {
  let timer = null;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

function throttle(fn, limit) {
  let inThrottle = false;
  return function (...args) {
    if (!inThrottle) {
      fn.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

// 防抖版统计刷新（避免频繁loadStats）
const debouncedLoadStats = debounce(async () => {
  await loadStats();
}, 800);

// ============================================================
// 初始化
// ============================================================
document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  setupCountPicker();
  setupFileImport();
  setupTextImport();
  setupGroupControls();
  setupHomeworkControls();
  setupExportControls();
  setupClassManagement();
  setupExitButton();
  setupBrandBadge();
  setupDonateButton();
  setupReminder();
  setupAnalyticsControls();
  setupExamManagement();
  setupHomeworkTypeSelectors();

  // 恢复显示模式（兼容旧版 localStorage）
  try {
    const savedZone = localStorage.getItem("classtrack_zone_display");
    const savedPrivacy = localStorage.getItem("classtrack_privacy");
    if (savedZone === "auto") {
      State.displayMode = "auto";
    } else if (savedPrivacy === "1") {
      State.displayMode = "code";
    }
    updateDisplayModeUI();
  } catch (e) {}

  // 显示模式下拉菜单
  setupDisplayModeDropdown();

  await loadClasses();
  setTodayDate();
});

// ============================================================
// API
// ============================================================
// ============================================================
// API（带请求缓存）
// ============================================================
const API = (function () {
  const _cache = new Map();  // key → { data, ts }
  const CACHE_TTL = 30000;   // 30 秒缓存（GET 请求）

  function _cacheKey(url) {
    return url;
  }

  async function get(url, opts = {}) {
    const { nocache = false } = opts;
    const key = _cacheKey(url);
    if (!nocache) {
      const hit = _cache.get(key);
      if (hit && Date.now() - hit.ts < CACHE_TTL) return hit.data;
    }
    const r = await fetch(url);
    const data = await r.json();
    if (!nocache) {
      _cache.set(key, { data, ts: Date.now() });
      // 限制缓存条目数
      if (_cache.size > 50) {
        const oldest = _cache.keys().next().value;
        _cache.delete(oldest);
      }
    }
    return data;
  }

  async function post(url, data = {}) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    // POST 会使相关缓存失效
    _bustRelated(url);
    if (r.headers.get("content-type")?.includes("application/json"))
      return r.json();
    return r;
  }

  async function put(url, data = {}) {
    const r = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    _bustRelated(url);
    return r.json();
  }

  async function del(url) {
    const r = await fetch(url, { method: "DELETE" });
    _bustRelated(url);
    return r.json();
  }

  async function upload(url, fd) {
    const r = await fetch(url, { method: "POST", body: fd });
    _bustRelated(url);
    return r.json();
  }

  // 写入操作使相关缓存失效
  function _bustRelated(url) {
    for (const key of _cache.keys()) {
      if (key.includes("/api/")) _cache.delete(key);
    }
  }

  // 手动清缓存
  function clearCache() {
    _cache.clear();
  }

  return { get, post, put, del, upload, clearCache };
})();

// ============================================================
// Toast — v2: 堆叠管理 + 上限5条
// ============================================================
const _toastTimers = new Map();

function showToast(msg, type = "info") {
  if (!msg) msg = "";
  const c = document.getElementById("toastContainer");
  // 超过 5 条时自动移除最早的一条
  while (c.children.length >= 5) {
    const oldest = c.firstElementChild;
    if (oldest) {
      oldest.classList.add("toast-out");
      const tid = _toastTimers.get(oldest);
      if (tid) { clearTimeout(tid); _toastTimers.delete(oldest); }
      oldest.addEventListener("animationend", () => oldest.remove(), { once: true });
    }
  }
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  const icon = { success: "✅", error: "❌", info: "ℹ️" }[type] || "ℹ️";
  t.innerHTML = `<span>${icon}</span> ${msg}`;
  c.appendChild(t);

  const tid = setTimeout(() => {
    t.classList.add("toast-out");
    t.addEventListener("animationend", () => {
      t.remove();
      _toastTimers.delete(t);
    }, { once: true });
  }, 2800);
  _toastTimers.set(t, tid);
}

// ============================================================
// 班级管理
// ============================================================
async function loadClasses() {
  const res = await API.get("/api/classes");
  if (res.code === 0) {
    State.classes = res.data;
    State.currentClassId = res.active_id;
    renderClassSelector();
    await loadAllData();
  }
}

function renderClassSelector() {
  const sel = document.getElementById("classSelect");
  sel.innerHTML = State.classes.map(c =>
    `<option value="${c.id}" ${c.id === State.currentClassId ? "selected" : ""}>${escapeHtml(c.name)}</option>`
  ).join("");
}

document.getElementById("classSelect").addEventListener("change", async function () {
  const cid = parseInt(this.value);
  if (cid === State.currentClassId) return;
  await API.post(`/api/classes/${cid}/activate`);
  State.currentClassId = cid;
  State.homeworkCache = {};
  State.selectedStudents.clear();
  await loadAllData();
  if (typeof resetAIContext === "function") resetAIContext();
  if (State.activeTab === "homework") renderHomeworkView();
  if (State.activeTab === "analytics") loadAnalytics();
  showToast("已切换班级", "info");
});

function setupClassManagement() {
  document.getElementById("btnClassManage").addEventListener("click", openClassModal);
  document.getElementById("btnClassModalClose").addEventListener("click", () => closeModal("classModal"));
  document.getElementById("btnAddClass").addEventListener("click", addClass);
  document.getElementById("newClassName").addEventListener("keydown", e => { if (e.key === "Enter") addClass(); });
}

function openClassModal() {
  const list = document.getElementById("classList");
  list.innerHTML = State.classes.map(c => `
    <div class="class-item">
      <span class="class-item-name">${escapeHtml(c.name)} ${c.id === State.currentClassId ? '<span class="class-btn-active">当前</span>' : ''}</span>
      <div class="class-item-actions">
        <button class="class-btn-rename" data-id="${c.id}">重命名</button>
        ${State.classes.length > 1 ? `<button class="class-btn-delete" data-id="${c.id}">删除</button>` : ''}
      </div>
    </div>
  `).join("");
  list.querySelectorAll(".class-btn-rename").forEach(b => b.addEventListener("click", () => renameClass(parseInt(b.dataset.id))));
  list.querySelectorAll(".class-btn-delete").forEach(b => b.addEventListener("click", () => deleteClass(parseInt(b.dataset.id))));
  document.getElementById("newClassName").value = "";
  document.getElementById("classModal").style.display = "";
}

async function addClass() {
  const input = document.getElementById("newClassName");
  const name = input.value.trim();
  if (!name) { showToast("请输入班级名称", "error"); return; }
  const res = await API.post("/api/classes", { name });
  if (res.code === 0) { showToast(res.msg, "success"); input.value = ""; await loadClasses(); openClassModal(); }
  else showToast(res.msg, "error");
}

async function renameClass(cid) {
  const name = prompt("请输入新的班级名称：");
  if (!name || !name.trim()) return;
  const res = await API.put(`/api/classes/${cid}`, { name: name.trim() });
  if (res.code === 0) { showToast(res.msg, "success"); await loadClasses(); }
  else showToast(res.msg, "error");
}

async function deleteClass(cid) {
  if (!confirm("删除班级将同时删除该班级的所有学生、分组和作业记录，确定继续？")) return;
  const res = await API.del(`/api/classes/${cid}`);
  if (res.code === 0) { showToast(res.msg, "success"); await loadClasses(); }
  else showToast(res.msg, "error");
}

// ============================================================
// 退出程序
// ============================================================
function setupExitButton() {
  document.getElementById("btnExit").addEventListener("click", async () => {
    if (!confirm("确定要退出 ClassTrack 吗？")) return;
    try { await API.post("/api/shutdown"); } catch (e) {}
    window.close();
    showToast("程序已退出，请关闭浏览器标签页", "info");
  });
}

// ============================================================
// 品牌商标弹窗
// ============================================================
function setupBrandBadge() {
  const badge = document.getElementById("brandBadge");
  const modal = document.getElementById("brandModal");
  const btnClose = document.getElementById("btnBrandClose");
  if (!badge || !modal) return;

  badge.addEventListener("click", () => {
    modal.style.display = "flex";
  });
  btnClose.addEventListener("click", () => {
    modal.style.display = "none";
  });
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.style.display = "none";
  });
}


// ============================================================
// 打赏弹窗
// ============================================================
function setupDonateButton() {
  const btn = document.getElementById("btnDonate");
  const modal = document.getElementById("donateModal");
  const btnClose = document.getElementById("btnDonateClose");
  if (!btn || !modal) return;

  btn.addEventListener("click", () => {
    modal.style.display = "flex";
  });
  btnClose.addEventListener("click", () => {
    modal.style.display = "none";
  });
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.style.display = "none";
  });
}
// ============================================================
// 确认对话框
// ============================================================
let confirmCallback = null;
function showConfirm(msg, cb) {
  document.getElementById("confirmMsg").textContent = msg;
  document.getElementById("confirmModal").style.display = "";
  confirmCallback = cb;
}
document.getElementById("btnConfirmClose").addEventListener("click", () => { document.getElementById("confirmModal").style.display = "none"; confirmCallback = null; });
document.getElementById("btnConfirmCancel").addEventListener("click", () => { document.getElementById("confirmModal").style.display = "none"; confirmCallback = null; });
document.getElementById("btnConfirmOk").addEventListener("click", () => {
  document.getElementById("confirmModal").style.display = "none";
  if (confirmCallback) { confirmCallback(); confirmCallback = null; }
});
/** v2 优化: 弹窗退出动画 */
function closeModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  // 先加退出动画类，动画结束后再隐藏
  modal.classList.add("modal-closing");
  const onAnimEnd = () => {
    modal.style.display = "none";
    modal.classList.remove("modal-closing");
    modal.removeEventListener("animationend", onAnimEnd);
  };
  modal.addEventListener("animationend", onAnimEnd);
}

// ============================================================
// Tab 切换
// ============================================================
function setupTabs() {
  // v2: 创建滑动指示器
  const nav = document.querySelector(".tab-nav");
  if (nav && !nav.querySelector(".tab-indicator")) {
    const indicator = document.createElement("div");
    indicator.className = "tab-indicator";
    nav.appendChild(indicator);
  }

  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // 初始定位 & 窗口 resize 重算
  updateTabIndicator();
  window.addEventListener("resize", debounce(updateTabIndicator, 100));
}

/** v2: 更新 tab 滑动指示器位置与宽度 */
function updateTabIndicator() {
  const indicator = document.querySelector(".tab-indicator");
  const activeBtn = document.querySelector(".tab-btn.active");
  if (!indicator || !activeBtn) return;
  const nav = activeBtn.closest(".tab-nav");
  if (!nav) return;
  const btnRect = activeBtn.getBoundingClientRect();
  const navRect = nav.getBoundingClientRect();
  indicator.style.transform = `translateX(${btnRect.left - navRect.left}px)`;
  indicator.style.width = `${btnRect.width}px`;
}
function switchTab(tabName) {
  const map = { grouping: "tabGrouping", homework: "tabHomework", exams: "tabExams", export: "tabExport", analytics: "tabAnalytics", settings: "tabSettings", aichat: "tabAIChat" };
  const nextSec = document.getElementById(map[tabName]);
  if (!nextSec) return;

  // v1.6 修复"每切一次页面闪两下"：
  // 旧实现是先播退出动画再播入场动画（两次闪烁），且 animationend 会从子元素
  // 冒泡导致切换时机错乱。改为即时切换 + 单次入场淡入。
  const sameTab = State.activeTab === tabName;

  State.activeTab = tabName;
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === tabName));

  if (!sameTab) {
    // 只有真正切页时才重放入场动画（同一 JS 任务内 remove+add 不会重启动画）
    document.querySelectorAll(".tab-content").forEach(s => s.classList.remove("active"));
    nextSec.classList.add("active");
  }
  updateTabIndicator(); // v2: 滑动指示器跟随
  if (tabName === "homework") { renderHomeworkView(); switchHWSubtab(State.hwSubtab); }
  if (tabName === "exams") renderExamView();
  if (tabName === "export") prepareExportTab();
  if (tabName === "grouping") { renderGroupingView(); updateSelectionUI(); }
  if (tabName === "analytics") { setAnalyticsToday(); loadAnalytics(); }
  if (tabName === "settings") { if (typeof loadAIConfig === 'function') loadAIConfig(); }
  if (tabName === "aichat") {
    if (typeof AIState !== 'undefined' && AIState.currentChart) {
      setTimeout(() => AIState.currentChart.resize(), 300);
    }
  }
}

// 刷新当前视图（用于隐私模式切换后即时刷新）
function refreshCurrentView() {
  if (State.activeTab === "homework") { _lastHomeworkHash = ''; renderHomeworkView(true); switchHWSubtab(State.hwSubtab); }
  if (State.activeTab === "export") prepareExportTab();
  if (State.activeTab === "grouping") { renderGroupingView(); updateSelectionUI(); }
  if (State.activeTab === "analytics") { loadAnalytics(); }
}

// 作业登记子Tab切换
function switchHWSubtab(subtab) {
  State.hwSubtab = subtab;
  // 更新按钮状态
  document.querySelectorAll('.hw-subtab-btn').forEach(b => b.classList.toggle('active', b.dataset.hwSubtab === subtab));
  // 隐藏所有面板
  ['hwManualPanel', 'hwPcScanPanel', 'hwMobilePanel'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  // 显示目标面板
  const panelMap = { manual: 'hwManualPanel', pcscan: 'hwPcScanPanel', mobile: 'hwMobilePanel' };
  const panel = document.getElementById(panelMap[subtab]);
  if (panel) panel.style.display = '';

  // 手机扫码子Tab：启动轮询
  if (subtab === 'mobile') {
    startMobilePolling();
  } else {
    stopMobilePolling();
  }
}

// ============================================================
// 数据加载
// ============================================================
async function loadAllData() {
  // 先加载学生数据，再加载分组（loadGroups 渲染时依赖 State.students）
  await loadStudents();
  await Promise.all([loadGroups(), loadStats(), loadHomeworkTypes()]);
}

async function loadHomeworkTypes() {
  const res = await API.get(`/api/homework-types`);
  if (res.code === 0) {
    State.homeworkTypes = res.data;
    if (State.homeworkTypes.length > 0 && !State.homeworkTypes.find(t => t.id === State.currentHomeworkTypeId)) {
      State.currentHomeworkTypeId = State.homeworkTypes[0].id;
    }
    renderHomeworkTypeSelectors();
  }
}

function renderHomeworkTypeSelectors() {
  const types = State.homeworkTypes;
  if (types.length === 0) return;
  const options = types.map(t =>
    `<option value="${t.id}" ${t.id === State.currentHomeworkTypeId ? 'selected' : ''}>${escapeHtml(t.name)}</option>`
  ).join('');

  ['homeworkTypeSelect', 'scanTypeSelect', 'analyticsTypeSelect'].forEach(id => {
    const sel = document.getElementById(id);
    if (sel) sel.innerHTML = options;
  });

  // 同步更新 AI 助手中的作业种类选择器（保留"全部种类"选项）
  const aiSel = document.getElementById('aiHomeworkTypeSelect');
  if (aiSel) {
    aiSel.innerHTML = '<option value="0">全部种类</option>' + types.map(t =>
      `<option value="${t.id}" ${t.id === State.currentHomeworkTypeId ? 'selected' : ''}>${escapeHtml(t.name)}</option>`
    ).join('');
  }
}

function syncHomeworkTypeSelectors() {
  ['homeworkTypeSelect', 'scanTypeSelect', 'analyticsTypeSelect'].forEach(id => {
    const sel = document.getElementById(id);
    if (sel) sel.value = State.currentHomeworkTypeId;
  });
  // 同步 AI 助手选择器
  const aiSel = document.getElementById('aiHomeworkTypeSelect');
  if (aiSel) aiSel.value = State.currentHomeworkTypeId || 0;
}

function setupHomeworkTypeSelectors() {
  // 作业登记页种类切换
  const hwSel = document.getElementById('homeworkTypeSelect');
  if (hwSel) {
    hwSel.addEventListener('change', () => {
      State.currentHomeworkTypeId = parseInt(hwSel.value);
      syncHomeworkTypeSelectors();
      renderHomeworkView(true);
    });
  }

  // 扫码页种类切换
  const scanSel = document.getElementById('scanTypeSelect');
  if (scanSel) {
    scanSel.addEventListener('change', () => {
      State.currentHomeworkTypeId = parseInt(scanSel.value);
      syncHomeworkTypeSelectors();
    });
  }

  // 数据概览页种类切换
  const analyticsSel = document.getElementById('analyticsTypeSelect');
  if (analyticsSel) {
    analyticsSel.addEventListener('change', () => {
      State.currentHomeworkTypeId = parseInt(analyticsSel.value);
      syncHomeworkTypeSelectors();
      loadAnalytics();
    });
  }

  // 管理按钮
  document.querySelectorAll('.btn-manage-hw-types').forEach(btn => {
    btn.addEventListener('click', openHWTypeModal);
  });
}

function openHWTypeModal() {
  let modal = document.getElementById('hwTypeModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'hwTypeModal';
    modal.innerHTML =
      '<div class="modal-card">' +
      '<div class="modal-header"><h3>📋 管理作业种类</h3><button class="modal-close" id="btnHWTypeClose">✕</button></div>' +
      '<div class="modal-body">' +
      '<div id="hwTypeList" style="max-height:300px;overflow-y:auto;margin-bottom:12px"></div>' +
      '<div style="display:flex;gap:8px">' +
      '<input type="text" id="newHWTypeName" placeholder="新种类名称" style="flex:1;padding:8px 12px;border:1px solid rgba(200,190,185,0.3);border-radius:8px;font-size:.85rem">' +
      '<button class="btn btn-primary" id="btnAddHWType">＋ 添加</button>' +
      '</div></div></div>';
    document.body.appendChild(modal);
    modal.querySelector('#btnHWTypeClose').addEventListener('click', () => modal.style.display = 'none');
    modal.addEventListener('click', e => { if (e.target === modal) modal.style.display = 'none'; });
    modal.querySelector('#btnAddHWType').addEventListener('click', addHWType);
    modal.querySelector('#newHWTypeName').addEventListener('keydown', e => { if (e.key === 'Enter') addHWType(); });
  }
  renderHWTypeList();
  modal.style.display = '';
}

function renderHWTypeList() {
  const list = document.getElementById('hwTypeList');
  if (!list) return;
  list.innerHTML = State.homeworkTypes.map(t => `
    <div class="class-item">
      <span class="class-item-name">${escapeHtml(t.name)} ${t.id === State.currentHomeworkTypeId ? '<span class="class-btn-active">当前</span>' : ''}</span>
      <div class="class-item-actions">
        <button class="class-btn-rename" data-id="${t.id}">重命名</button>
        ${State.homeworkTypes.length > 1 ? `<button class="class-btn-delete" data-id="${t.id}">删除</button>` : ''}
      </div>
    </div>
  `).join('');
  list.querySelectorAll('.class-btn-rename').forEach(b => b.addEventListener('click', () => renameHWType(parseInt(b.dataset.id))));
  list.querySelectorAll('.class-btn-delete').forEach(b => b.addEventListener('click', () => deleteHWType(parseInt(b.dataset.id))));
}

async function addHWType() {
  const input = document.getElementById('newHWTypeName');
  const name = input.value.trim();
  if (!name) { showToast('请输入名称', 'error'); return; }
  const res = await API.post('/api/homework-types', { name });
  if (res.code === 0) { showToast(res.msg, 'success'); input.value = ''; await loadHomeworkTypes(); renderHWTypeList(); }
  else showToast(res.msg, 'error');
}

async function renameHWType(tid) {
  const name = prompt('请输入新名称：');
  if (!name || !name.trim()) return;
  const res = await API.put(`/api/homework-types/${tid}`, { name: name.trim() });
  if (res.code === 0) { showToast(res.msg, 'success'); await loadHomeworkTypes(); }
  else showToast(res.msg, 'error');
}

async function deleteHWType(tid) {
  if (!confirm('确定删除该作业种类？')) return;
  const res = await API.del(`/api/homework-types/${tid}`);
  if (res.code === 0) {
    showToast(res.msg, 'success');
    await loadHomeworkTypes();
    if (State.currentHomeworkTypeId === tid) {
      State.currentHomeworkTypeId = State.homeworkTypes[0]?.id || 1;
      syncHomeworkTypeSelectors();
      renderHomeworkView(true);
    }
  } else showToast(res.msg, 'error');
}

async function loadStudents() {
  const res = await API.get(`/api/students?class_id=${State.currentClassId}`);
  if (res.code === 0) { State.students = res.data; updatePoolCount(); }
}

async function loadGroups() {
  const res = await API.get(`/api/groups?class_id=${State.currentClassId}`);
  if (res.code === 0) {
    State.groups = res.data.groups || [];
    State.unassigned = res.data.unassigned || [];
    State.selectedCount = State.groups.length || 6;
    updateGroupCountUI();
    updateStatsDisplay();
    // Always update pool count; render grouping view regardless of active tab
    // (rendering into a display:none container is cheap and ensures data consistency)
    try {
      renderGroupingView();
    } catch (e) {
      console.error("renderGroupingView error:", e);
      if (!window.__groupViewErrorShown) {
        window.__groupViewErrorShown = true;
        showToast("分组视图渲染出错，请刷新页面或更换浏览器", "error");
      }
      updatePoolCount();
    }
  }
}

async function loadStats(statsData) {
  const tid = State.currentHomeworkTypeId;
  const res = statsData ? { code: 0, data: statsData } : await API.get(`/api/stats?class_id=${State.currentClassId}&homework_type_id=${tid}`);
  if (res.code === 0) updateStatsDisplay(res.data);
}

async function loadHomeworkForDate(date) {
  const tid = State.currentHomeworkTypeId;
  const res = await API.get(`/api/homework?date=${date}&class_id=${State.currentClassId}&homework_type_id=${tid}`);
  if (res.code === 0) State.homeworkCache[cacheKey(date, tid)] = res.data;
}

// ============================================================
// 统计显示
// ============================================================
function updateStatsDisplay(data) {
  if (!data) return;
  // 统计徽章已从头部移除，仅更新锁定状态
  const lockDot = document.querySelector(".lock-dot");
  const lockText = document.getElementById("lockStatusText");
  // v1.5: 以后端返回的 is_locked 为准（旧版接口用 last_lock_time 兼容推断）
  const isLocked = (data.is_locked !== undefined) ? !!data.is_locked
                 : !!(data.last_lock_time && data.last_lock_time !== "尚未锁定");
  State.isLocked = isLocked;
  if (isLocked) {
    if (lockDot) lockDot.classList.add("locked");
    if (lockText) lockText.textContent = `分组状态：已锁定 (${data.last_lock_time || ""})`;
  } else {
    if (lockDot) lockDot.classList.remove("locked");
    if (lockText) lockText.textContent = "分组状态：未锁定";
  }
  // 锁定/解锁按钮互斥显示
  const lockBtn = document.getElementById("btnLockGroups");
  const unlockBtn = document.getElementById("btnUnlockGroups");
  if (lockBtn) lockBtn.style.display = isLocked ? "none" : "";
  if (unlockBtn) unlockBtn.style.display = isLocked ? "" : "none";
}

// ============================================================
// Excel 导入
// ============================================================
function setupFileImport() {
  const fi = document.getElementById("fileInput");
  const ul = document.getElementById("uploadLabel");
  ul.addEventListener("click", () => fi.click());
  fi.addEventListener("change", handleFileImport);
  ul.addEventListener("dragover", e => { e.preventDefault(); ul.style.border = "2px dashed var(--blue)"; ul.style.background = "var(--blue-pale)"; });
  ul.addEventListener("dragleave", () => { ul.style.border = ""; ul.style.background = ""; });
  ul.addEventListener("drop", e => {
    e.preventDefault(); ul.style.border = ""; ul.style.background = "";
    if (e.dataTransfer.files.length > 0) { fi.files = e.dataTransfer.files; handleFileImport(); }
  });
}

async function handleFileImport() {
  const fi = document.getElementById("fileInput");
  const st = document.getElementById("importStatus");
  const file = fi.files[0]; if (!file) return;
  const fd = new FormData(); fd.append("file", file);
  st.textContent = "⏳ 正在导入..."; st.style.color = "var(--text-light)";
  try {
    const res = await API.upload(`/api/import?class_id=${State.currentClassId}`, fd);
    if (res.code === 0) {
      st.textContent = `✅ ${res.msg}`; st.style.color = "var(--green)";
      showToast(res.msg, "success");
      if (State.groups.length === 0) await API.post(`/api/groups/init?class_id=${State.currentClassId}`, { count: State.selectedCount });
      await loadAllData();
    } else {
      st.textContent = `❌ ${res.msg}`; st.style.color = "var(--pink)";
      showToast(res.msg, "error");
    }
  } catch (e) {
    st.textContent = "❌ 导入失败"; st.style.color = "var(--pink)";
  }
  fi.value = "";
  setTimeout(() => { if (st.textContent.startsWith("✅")) st.textContent = ""; }, 5000);
}

// ============================================================
// 文字导入 (v1.2: 支持自动识别学号)
// ============================================================
function setupTextImport() {
  document.querySelectorAll(".import-mode-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      State.importMode = btn.dataset.mode;
      document.querySelectorAll(".import-mode-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("importExcelPanel").style.display = State.importMode === "excel" ? "" : "none";
      document.getElementById("importTextPanel").style.display = State.importMode === "text" ? "" : "none";
    });
  });

  document.getElementById("importTextarea").addEventListener("input", () => {
    const text = document.getElementById("importTextarea").value;
    const parsed = parseTextNamesWithCodes(text);
    const withCodes = parsed.filter(p => p.code).length;
    // 构建预览文本：前10条展开，超出用省略号
    const previewItems = parsed.slice(0, 10).map(p =>
      p.code ? `<span class="parsed-item">${escapeHtml(p.code)} ${escapeHtml(p.name)}</span>` : `<span class="parsed-item">${escapeHtml(p.name)}</span>`
    );
    const more = parsed.length > 10 ? ` 等${parsed.length}条` : '';
    const label = parsed.length === 0
      ? '已识别 0 条'
      : `已识别 <strong>${parsed.length}</strong> 条${withCodes > 0 ? `（含学号 ${withCodes} 条）` : ''}：${previewItems.join('、')}${more}`;
    document.getElementById("importTextCount").innerHTML = label;
  });

  document.getElementById("btnImportText").addEventListener("click", async () => {
    const text = document.getElementById("importTextarea").value;
    if (!text.trim()) { showToast("请输入学生姓名", "error"); return; }
    const parsed = parseTextNamesWithCodes(text);
    if (parsed.length === 0) { showToast("未能解析出有效记录", "error"); return; }
    const res = await API.post("/api/import/text", { text, class_id: State.currentClassId, parsed_records: parsed });
    if (res.code === 0) {
      showToast(res.msg, "success");
      document.getElementById("importTextarea").value = "";
      document.getElementById("importTextCount").textContent = "已识别 0 条记录";
      if (State.groups.length === 0) await API.post(`/api/groups/init?class_id=${State.currentClassId}`, { count: State.selectedCount });
      await loadAllData();
    } else showToast(res.msg, "error");
  });
}

/**
 * 解析文字输入，自动识别学号
 * 支持格式（每行一条记录）：
 *   "001 张三" — 学号+空格+姓名（最常见，推荐格式）
 *   "1 张三" / "01 张三" — 学号位数不限
 *   "张三 001" — 姓名在前，学号在后
 *   "001-张三" / "张三-001" — 连字符分隔
 *   "张三(001)" / "张三（001）" — 括号标注学号
 *   Tab 分隔（从 Excel 粘贴）
 *   纯姓名（无学号）— 自动识别，不设学号
 *   "学号:001 姓名:张三" — 标签格式自动清洗
 *
 * 核心设计：每行 = 一个学生，绝不把空格分隔的词拆成多名学生
 */
function parseTextNamesWithCodes(text) {
  // 去除BOM、首尾空白
  text = text.replace(/^﻿/, '').trim();
  if (!text) return [];

  // 按行分割（支持 CR/LF/CRLF）
  const lines = text.split(/[\n\r]+/).map(l => l.trim()).filter(Boolean);
  const results = [];
  const seenNames = new Set();

  // 预处理函数：清洗标签前缀
  function cleanLine(s) {
    return s
      .replace(/学号\s*[:：]\s*/gi, '')
      .replace(/姓名\s*[:：]\s*/gi, '')
      .replace(/编号\s*[:：]\s*/gi, '')
      .replace(/^No\.?\s*/i, '')
      .trim();
  }

  for (let rawLine of lines) {
    let line = cleanLine(rawLine);
    if (!line) continue;

    // 跳过纯表头行
    if (/^(学号|姓名|编号|序号|学生|name|code|id)$/i.test(line)) continue;

    // ──── 模式1: 数字开头 + 空白 + 名字（"001 张三"）────
    let m = line.match(/^(\d{1,20})\s+(.+)$/);
    if (m) {
      const code = m[1];
      const name = m[2].replace(/[（(]\d+[）)]/g, '').trim();
      if (name && !/^\d+$/.test(name) && !seenNames.has(name)) {
        seenNames.add(name);
        results.push({ name, code });
      }
      continue;
    }

    // ──── 模式2: 名字 + 空白 + 数字结尾（"张三 001"）────
    m = line.match(/^(.+?)\s+(\d{1,20})$/);
    if (m) {
      const name = m[1].replace(/[（(]\d+[）)]/g, '').trim();
      const code = m[2];
      if (name && !/^\d+$/.test(name) && !seenNames.has(name)) {
        seenNames.add(name);
        results.push({ name, code });
      }
      continue;
    }

    // ──── 模式3: 数字-名字 或 名字-数字 ────
    m = line.match(/^(\d{1,20})-(.+)$/) || line.match(/^(.+)-(\d{1,20})$/);
    if (m) {
      const isCodeFirst = /^\d+$/.test(m[1]);
      const code = isCodeFirst ? m[1] : m[2];
      const name = (isCodeFirst ? m[2] : m[1]).trim();
      if (name && !/^\d+$/.test(name) && !seenNames.has(name)) {
        seenNames.add(name);
        results.push({ name, code });
      }
      continue;
    }

    // ──── 模式4: 名字(学号) 或 名字（学号）────
    m = line.match(/^(.+?)[（(](\d{1,20})[）)]\s*$/);
    if (m) {
      const name = m[1].trim();
      const code = m[2];
      if (name && !/^\d+$/.test(name) && !seenNames.has(name)) {
        seenNames.add(name);
        results.push({ name, code });
      }
      continue;
    }

    // ──── 模式5: Tab分隔（从Excel粘贴）────
    if (line.includes('\t')) {
      const tabs = line.split(/\t+/).map(p => p.trim()).filter(Boolean);
      if (tabs.length >= 2) {
        const t0IsNum = /^\d+$/.test(tabs[0]);
        const code = t0IsNum ? tabs[0] : (/^\d+$/.test(tabs[1]) ? tabs[1] : '');
        const nameIdx = t0IsNum ? 1 : 0;
        const name = tabs[nameIdx].replace(/[（(]\d+[）)]/g, '').trim();
        if (name && !/^\d+$/.test(name) && !seenNames.has(name)) {
          seenNames.add(name);
          results.push({ name, code });
        }
      }
      continue;
    }

    // ──── 模式6: 逗号/顿号分隔的多条记录 ────
    if (/[,，、]/.test(line)) {
      const parts = line.split(/[,，、]+/).map(p => p.trim()).filter(Boolean);
      for (const part of parts) {
        // 每条再尝试 "数字+空格+名字"
        const pm = part.match(/^(\d{1,20})\s+(.+)$/);
        if (pm) {
          const name = pm[2].replace(/[（(]\d+[）)]/g, '').trim();
          if (name && !/^\d+$/.test(name) && !seenNames.has(name)) {
            seenNames.add(name);
            results.push({ name, code: pm[1] });
          }
          continue;
        }
        // 纯姓名
        const name = part.replace(/[（(]\d+[）)]/g, '').trim();
        if (name && !/^\d+$/.test(name) && !seenNames.has(name)) {
          seenNames.add(name);
          results.push({ name, code: '' });
        }
      }
      continue;
    }

    // ──── 模式7: 纯姓名（无学号）────
    // 关键：只要不全是数字，就当作姓名
    const name = line.replace(/[（(]\d+[）)]/g, '').trim();
    if (name && !/^\d+$/.test(name) && !seenNames.has(name)) {
      seenNames.add(name);
      results.push({ name, code: '' });
    }
  }
  return results;
}

// 保留旧版兼容函数
function parseTextNames(text) {
  const parsed = parseTextNamesWithCodes(text);
  return parsed.map(p => p.name);
}

// ============================================================
// 分组控制
// ============================================================
function setupCountPicker() {
  document.querySelectorAll(".count-btn[data-count]").forEach(btn => {
    btn.addEventListener("click", () => { State.selectedCount = parseInt(btn.dataset.count); updateGroupCountUI(); });
  });
  document.getElementById("btnApplyCount").addEventListener("click", async () => {
    const v = parseInt(document.getElementById("customCount").value);
    if (v >= 2 && v <= 20) { State.selectedCount = v; updateGroupCountUI(); await applyGroupCount(); document.getElementById("customCount").value = ""; }
    else if (document.getElementById("customCount").value.trim()) showToast("请输入2-20之间的数字", "error");
  });
  document.getElementById("customCount").addEventListener("keydown", e => { if (e.key === "Enter") document.getElementById("btnApplyCount").click(); });
}

function updateGroupCountUI() {
  document.querySelectorAll(".count-btn[data-count]").forEach(b => b.classList.toggle("active", parseInt(b.dataset.count) === State.selectedCount));
}

async function applyGroupCount() {
  const res = await API.post(`/api/groups/init?class_id=${State.currentClassId}`, { count: State.selectedCount });
  if (res.code === 0) { showToast(res.msg, "success"); await loadAllData(); }
  else showToast(res.msg, "error");
}

function setupGroupControls() {
  document.getElementById("btnLockGroups").addEventListener("click", async () => {
    const saved = await saveCurrentGrouping();
    if (!saved) { showToast("分组保存失败，未锁定", "error"); return; }
    const res = await API.post(`/api/groups/lock?class_id=${State.currentClassId}`);
    if (res.code === 0) { State.isLocked = true; showToast("分组已锁定！✅", "success"); await loadAllData(); }
    else showToast(res.msg || "锁定失败，请重试", "error");
  });
  const unlockBtn = document.getElementById("btnUnlockGroups");
  if (unlockBtn) unlockBtn.addEventListener("click", async () => {
    const res = await API.post(`/api/groups/unlock?class_id=${State.currentClassId}`);
    if (res.code === 0) { State.isLocked = false; showToast("分组已解锁 ✅", "success"); await loadAllData(); }
    else showToast(res.msg || "解锁失败，请重试", "error");
  });
  document.getElementById("btnResetGroups").addEventListener("click", async () => {
    if (!confirm("确定重新分组？所有学生将回到未分组状态。")) return;
    const res = await API.post(`/api/groups/reset?class_id=${State.currentClassId}`);
    if (res.code === 0) {
      showToast("已重置", "info");
      // applyGroupCount 内部成功时已 loadAllData，这里再调一次会连续
      // 渲染两遍（入场动画跑两次，页面闪两下），故移除重复调用
      await applyGroupCount();
      State.selectedStudents.clear(); updateSelectionUI();
    } else showToast(res.msg || "重置失败，请重试", "error");
  });
  document.getElementById("btnSelectAll").addEventListener("click", selectAll);
  document.getElementById("btnDeselectAll").addEventListener("click", deselectAll);
  document.getElementById("btnClearSelection").addEventListener("click", deselectAll);
  document.getElementById("btnExportGroups").addEventListener("click", exportGroups);
  // v1.3: 清空名单池
  document.getElementById("btnClearPool").addEventListener("click", clearUnassignedPool);
  // v1.3: 删除选中
  document.getElementById("btnDeleteSelected").addEventListener("click", deleteSelectedStudents);
}

async function saveCurrentGrouping() {
  // v1.5 修复：整张分组表一次性提交（单事务），避免并发请求
  // 部分成功部分失败导致"保存了但没保存上"的问题
  const groups = [];
  const cols = document.querySelectorAll(".group-column");
  for (const col of cols) {
    const gid = parseInt(col.dataset.groupId);
    if (isNaN(gid)) continue;
    const cards = col.querySelectorAll(".student-card");
    groups.push({ group_id: gid, student_ids: [...cards].map(c => parseInt(c.dataset.studentId)) });
  }
  // 未分组池中的学生统一归零
  const poolCards = document.querySelectorAll("#unassignedPool .student-card");
  if (poolCards.length > 0) {
    groups.push({ group_id: 0, student_ids: [...poolCards].map(c => parseInt(c.dataset.studentId)) });
  }
  if (groups.length === 0) return true;
  try {
    const res = await API.post(`/api/groups/save?class_id=${State.currentClassId}`, { groups });
    if (res.code === 0) {
      showToast(res.msg, "success");
      return true;
    }
    showToast(res.msg || "分组保存失败，请重试", "error");
    return false;
  } catch (e) {
    showToast("分组保存失败，请检查网络后重试", "error");
    return false;
  }
}

// ============================================================
// 多选系统
// ============================================================
function toggleSelect(studentId, e) {
  if (e.ctrlKey || e.metaKey) {
    if (State.selectedStudents.has(studentId)) State.selectedStudents.delete(studentId);
    else State.selectedStudents.add(studentId);
  } else if (e.shiftKey && State.selectedStudents.size > 0) {
    const container = e.target.closest(".group-students") || e.target.closest(".unassigned-pool");
    if (container) {
      const cards = [...container.querySelectorAll(".student-card")];
      const clickedIdx = cards.findIndex(c => parseInt(c.dataset.studentId) === studentId);
      const lastSelected = [...State.selectedStudents].pop();
      const lastIdx = cards.findIndex(c => parseInt(c.dataset.studentId) === lastSelected);
      if (clickedIdx >= 0 && lastIdx >= 0) {
        const [from, to] = [Math.min(clickedIdx, lastIdx), Math.max(clickedIdx, lastIdx)];
        for (let i = from; i <= to; i++) State.selectedStudents.add(parseInt(cards[i].dataset.studentId));
      }
    }
  } else {
    if (State.selectedStudents.has(studentId)) State.selectedStudents.delete(studentId);
    else State.selectedStudents.add(studentId);
  }
  updateSelectionUI();
  refreshCardSelectionStyles();
}

function selectAll() {
  State.students.forEach(s => State.selectedStudents.add(s.id));
  updateSelectionUI();
  refreshCardSelectionStyles();
}

function deselectAll() {
  State.selectedStudents.clear();
  updateSelectionUI();
  refreshCardSelectionStyles();
}

function updateSelectionUI() {
  const count = State.selectedStudents.size;
  const info = document.getElementById("selectionInfo");
  const toolbar = document.getElementById("selectToolbar");
  if (count > 0) {
    info.style.display = ""; toolbar.style.display = "";
    document.getElementById("selCount").textContent = count;
  } else {
    info.style.display = "none"; toolbar.style.display = "none";
  }
}

function refreshCardSelectionStyles() {
  document.querySelectorAll(".student-card").forEach(card => {
    const sid = parseInt(card.dataset.studentId);
    card.classList.toggle("selected", State.selectedStudents.has(sid));
  });
}

// ============================================================
// 分组视图渲染 (v1.2: 学号显示)
// ============================================================
function renderGroupingView() {
  renderGroupColumns();
  renderUnassignedPool();
  updatePoolCount();
}

function renderGroupColumns() {
  const container = document.getElementById("groupsContainer");
  if (State.groups.length === 0) {
    container.innerHTML = `<div class="empty-state"><span class="empty-icon">👥</span><p>尚未设置分组</p></div>`;
    return;
  }
  const groupStudents = {};
  for (const g of State.groups) groupStudents[g.id] = [];
  for (const s of State.students) {
    if (s.group_id && groupStudents[s.group_id]) groupStudents[s.group_id].push(s);
  }
  container.innerHTML = State.groups.map(g => {
    const students = groupStudents[g.id] || [];
    return `<div class="group-column" data-group-id="${g.id}">
      <div class="group-column-header">
        <span class="group-name"><span class="group-name-dot" style="background:${g.color}"></span>${escapeHtml(g.name)}</span>
        <span class="group-student-count">${students.length}人</span>
      </div>
      <div class="group-students">
        ${students.length === 0 ? '<div class="group-empty-hint">拖拽学生到此处 👆</div>' : students.map((s, i) => renderStudentCard(s, g.color, i)).join("")}
      </div></div>`;
  }).join("");
  bindDragEvents();
  refreshCardSelectionStyles();
  // v2: 交错入场动画
  staggerEntrance(container, '.group-column', 50);
  // v2: 应用拖放弹跳动画
  if (_bounceStudentIds.length > 0) {
    const bounceSet = new Set(_bounceStudentIds);
    container.querySelectorAll('.student-card').forEach(card => {
      if (bounceSet.has(parseInt(card.dataset.studentId))) {
        card.classList.add('drop-bounce');
        card.addEventListener('animationend', () => card.classList.remove('drop-bounce'), { once: true });
      }
    });
    _bounceStudentIds = [];
  }
}

function renderStudentCard(student, groupColor, index) {
  const avatars = ["🐱","🐶","🐰","🐻","🦊","🐼","🐨","🐯","🦁","🐮","🐷","🐸","🐵","🐔","🦄","🐙","🦋","🐞","🐝","🦉"];
  const avatar = avatars[Math.abs(hashCode(student.name)) % avatars.length];
  const displayName = formatStudentDisplay(student.name, student.student_code);
  const codeHtml = formatStudentCodeHtml(student.student_code);
  return `<div class="student-card ${State.selectedStudents.has(student.id) ? 'selected' : ''}" draggable="true"
       data-student-id="${student.id}" data-student-name="${escapeHtml(displayName)}" data-group-id="${student.group_id || 0}"
       style="--card-color:${groupColor || 'var(--text-lighter)'}">
    <div class="student-avatar" style="background:${groupColor || 'var(--blue-pale)'}">${avatar}</div>
    ${codeHtml}
    <span class="student-name${privacyClass()}">${escapeHtml(displayName)}</span>
    <button class="btn-delete-student" data-sid="${student.id}" title="删除学生">✕</button>
  </div>`;
}

function renderUnassignedPool() {
  const pool = document.getElementById("unassignedPool");
  const unassigned = State.students.filter(s => !s.group_id || s.group_id === 0);
  if (unassigned.length === 0) {
    pool.innerHTML = `<div class="pool-placeholder"><span class="placeholder-icon">🎉</span><p>所有学生已分组完毕！</p></div>`;
  } else {
    pool.innerHTML = unassigned.map(s => renderStudentCard(s, "var(--text-lighter)", 0)).join("")
      + `<div class="pool-clear-area"><button class="btn btn-danger btn-pool-clear" id="btnClearPoolInline">🗑 一键清空名单池（${unassigned.length}人）</button></div>`;
    // 绑定内联清空按钮
    const btnInline = document.getElementById("btnClearPoolInline");
    if (btnInline) btnInline.addEventListener("click", clearUnassignedPool);
  }
  bindDragEvents();
  bindDeleteButtons();
  refreshCardSelectionStyles();
}

function updatePoolCount() {
  const unassigned = State.students.filter(s => !s.group_id || s.group_id === 0);
  document.getElementById("poolCount").textContent = `${unassigned.length}人`;
}

// ============================================================
// 删除学生
// ============================================================
function bindDeleteButtons() {
  document.querySelectorAll(".btn-delete-student").forEach(btn => {
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      const sid = parseInt(this.dataset.sid);
      const name = this.closest(".student-card")?.querySelector(".student-name")?.textContent || "";
      showConfirm(`确定要删除学生「${name}」吗？\n该操作不可恢复，相关作业记录也将一并删除。`, async () => {
        const res = await API.del(`/api/students/${sid}`);
        if (res.code === 0) {
          showToast(`已删除「${name}」`, "success");
          State.selectedStudents.delete(sid);
          updateSelectionUI();
          await loadAllData();
          if (State.activeTab === "homework") renderHomeworkView();
        } else showToast(res.msg, "error");
      });
    });
  });
}

// ============================================================
// 拖拽系统
// ============================================================
let dragStudentId = null;
let dragSourceGroupId = null;
let dragElement = null;
let isBatchDrag = false;
let _bounceStudentIds = [];  // v2: 记录需要弹跳动画的学生ID

let _dragDelegationSetup = false;
function ensureDragDelegation() {
  if (_dragDelegationSetup) return;
  _dragDelegationSetup = true;

  const groupsContainer = document.getElementById("groupsContainer");
  groupsContainer.addEventListener("dragover", function (e) {
    const col = e.target.closest(".group-column");
    if (!col) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    col.classList.add("drag-over");
  }, { passive: false });
  groupsContainer.addEventListener("dragleave", function (e) {
    const col = e.target.closest(".group-column");
    if (!col) return;
    if (!col.contains(e.relatedTarget)) col.classList.remove("drag-over");
  });
  groupsContainer.addEventListener("drop", async function (e) {
    const col = e.target.closest(".group-column");
    if (!col) return;
    e.preventDefault();
    col.classList.remove("drag-over");
    flashElement(col); // v2: 放置闪烁反馈
    if (State.isLocked) { showToast("分组已锁定，请先点击「解锁分组」", "error"); return; }
    const targetGroupId = parseInt(col.getAttribute("data-group-id"));
    if (isNaN(targetGroupId)) return;

    if (isBatchDrag) {
      await moveMultipleStudents([...State.selectedStudents], targetGroupId);
    } else {
      if (!dragStudentId || targetGroupId === dragSourceGroupId) return;
      await moveStudentToGroup(dragStudentId, targetGroupId);
    }
  });

  const pool = document.getElementById("unassignedPool");
  pool.addEventListener("dragover", function (e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    pool.classList.add("drag-over");
  }, { passive: false });
  pool.addEventListener("dragleave", function (e) {
    if (!pool.contains(e.relatedTarget)) pool.classList.remove("drag-over");
  });
  pool.addEventListener("drop", async function (e) {
    e.preventDefault();
    pool.classList.remove("drag-over");
    if (State.isLocked) { showToast("分组已锁定，请先点击「解锁分组」", "error"); return; }
    if (isBatchDrag) {
      await moveMultipleStudents([...State.selectedStudents], 0);
    } else {
      if (!dragStudentId) return;
      await moveStudentToGroup(dragStudentId, 0);
    }
  });
}

document.body.addEventListener("dragover", function (e) {
  const card = e.target.closest(".student-card");
  if (card && card !== dragElement) {
    e.preventDefault();
    card.classList.add("drag-over-card");
  }
}, { passive: false });
document.body.addEventListener("dragleave", function (e) {
  const card = e.target.closest(".student-card");
  if (card && !card.contains(e.relatedTarget)) {
    card.classList.remove("drag-over-card");
  }
});

function bindDragEvents() {
  ensureDragDelegation();
  // Per-card binding for both drag and click — delegation has browser-specific
  // issues with dragstart/dataTransfer and click-on-child-element edge cases
  const cards = document.querySelectorAll(".student-card[draggable]");
  cards.forEach(card => {
    card.removeEventListener("dragstart", onDragStart);
    card.removeEventListener("dragend", onDragEnd);
    card.addEventListener("dragstart", onDragStart);
    card.addEventListener("dragend", onDragEnd);
    card.removeEventListener("click", onCardClick);
    card.addEventListener("click", onCardClick);
  });
  bindDeleteButtons();
}

function onCardClick(e) {
  if (e.target.closest(".btn-delete-student")) return;
  const sid = parseInt(this.dataset.studentId);
  if (isNaN(sid)) return;
  toggleSelect(sid, e);
}

function onDragStart(e) {
  const sid = parseInt(this.dataset.studentId);
  dragStudentId = sid;
  dragSourceGroupId = parseInt(this.dataset.groupId || 0);
  dragElement = this;

  if (State.selectedStudents.has(sid) && State.selectedStudents.size > 1) {
    isBatchDrag = true;
    e.dataTransfer.setData("text/plain", JSON.stringify([...State.selectedStudents]));
    e.dataTransfer.effectAllowed = "move";
    const count = State.selectedStudents.size;
    const ghost = document.createElement("div");
    ghost.style.cssText = "position:absolute;top:-1000px;background:#7EB5D6;color:white;padding:6px 14px;border-radius:20px;font-size:14px;font-weight:700;white-space:nowrap;";
    ghost.textContent = `📦 移动 ${count} 名学生`;
    document.body.appendChild(ghost);
    e.dataTransfer.setDragImage(ghost, 50, 20);
    setTimeout(() => ghost.remove(), 0);
  } else {
    isBatchDrag = false;
    e.dataTransfer.setData("text/plain", sid.toString());
    e.dataTransfer.effectAllowed = "move";
  }
  this.classList.add("dragging");
}

function onDragEnd(e) {
  this.classList.remove("dragging");
  dragStudentId = null; dragSourceGroupId = null; dragElement = null; isBatchDrag = false;
  document.querySelectorAll(".drag-over,.drag-over-card").forEach(el => el.classList.remove("drag-over", "drag-over-card"));
}

async function moveStudentToGroup(studentId, groupId) {
  try {
    const res = await API.put(`/api/students/${studentId}/move`, { group_id: groupId });
    if (res.code === 0) {
      const student = State.students.find(s => s.id === studentId);
      if (student) student.group_id = groupId;
      _bounceStudentIds = [studentId];  // v2: 标记需要弹跳动画的学生
      await loadGroups();
    } else {
      // 保存失败：明确提示并重新渲染，避免"拖过去没反应"的静默失败
      showToast(res.msg || "保存失败，请重试", "error");
      await loadGroups();
    }
  } catch (e) { showToast("移动失败，请检查网络后重试", "error"); await loadGroups(); }
}

async function moveMultipleStudents(studentIds, groupId) {
  try {
    const res = await API.put("/api/students/batch-move", { student_ids: studentIds, group_id: groupId });
    if (res.code === 0) {
      showToast(res.msg, "success");
      for (const sid of studentIds) {
        const student = State.students.find(s => s.id === sid);
        if (student) student.group_id = groupId;
      }
      State.selectedStudents.clear();
      updateSelectionUI();
      _bounceStudentIds = [...studentIds];  // v2: 批量标记弹跳动画
      await loadGroups();
      refreshCardSelectionStyles();
    } else showToast(res.msg, "error");
  } catch (e) { showToast("批量移动失败", "error"); }
}

function exportGroups() {
  window.open(`/api/export/groups?class_id=${State.currentClassId}`, "_blank");
}

// v1.3: 清空未分组学生
async function clearUnassignedPool() {
  if (!State.students) { showToast("数据尚未加载，请稍后再试", "error"); return; }
  const unassigned = State.students.filter(s => !s.group_id || s.group_id === 0);
  if (unassigned.length === 0) { showToast("没有未分组的学生", "error"); return; }
  showConfirm(`确定要清空名单池吗？\n将删除全部 ${unassigned.length} 名未分组学生及其作业记录，此操作不可恢复。`, async () => {
    try {
      const res = await API.post(`/api/students/clear-unassigned?class_id=${State.currentClassId}`);
      if (res && res.code === 0) {
        showToast(res.msg || "已清除", "success");
        await loadAllData();
        if (State.activeTab === "homework") renderHomeworkView();
      } else {
        showToast((res && res.msg) || "操作失败", "error");
      }
    } catch (e) {
      showToast("网络错误，请重试", "error");
    }
  });
}

// v1.3: 删除选中的学生
async function deleteSelectedStudents() {
  const ids = [...State.selectedStudents];
  if (ids.length === 0) { showToast("没有选中的学生", "error"); return; }
  showConfirm(`确定要删除选中的 ${ids.length} 名学生吗？\n该操作不可恢复，相关作业记录也将一并删除。`, async () => {
    const res = await API.post("/api/students/batch-delete", { student_ids: ids });
    if (res.code === 0) {
      showToast(res.msg, "success");
      State.selectedStudents.clear();
      updateSelectionUI();
      await loadAllData();
      if (State.activeTab === "homework") renderHomeworkView();
    } else showToast(res.msg, "error");
  });
}

// ============================================================
// 作业登记 (v1.2: 即时UI更新 + 学号显示)
// ============================================================
function setTodayDate() {
  const today = new Date().toISOString().split("T")[0];
  const el = document.getElementById("homeworkDate");
  if (el) el.value = today;
}

function setupHomeworkControls() {
  const dateInput = document.getElementById("homeworkDate");
  dateInput.addEventListener("change", () => renderHomeworkView());
  document.getElementById("btnPrevDay").addEventListener("click", () => changeHomeworkDate(-1));
  document.getElementById("btnNextDay").addEventListener("click", () => changeHomeworkDate(1));
  document.getElementById("btnToday").addEventListener("click", () => { setTodayDate(); renderHomeworkView(); });
  document.querySelectorAll(".grade-batch-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const grade = btn.dataset.grade;
      const date = document.getElementById("homeworkDate").value;
      if (!date) return;
      if (!confirm(`确定将 ${date} 所有学生作业等级批量设为「${gradeDisplayLabel(grade)}」吗？`)) return;
      const res = await API.post("/api/homework/batch", { date, grade, class_id: State.currentClassId, homework_type_id: State.currentHomeworkTypeId });
      if (res.code === 0) { showToast("批量设置成功", "success"); State.homeworkCache[cacheKey(date, State.currentHomeworkTypeId)] = null; debouncedLoadStats(); renderHomeworkView(); }
      else showToast(res.msg, "error");
    });
  });
}

function changeHomeworkDate(delta) {
  const di = document.getElementById("homeworkDate");
  const d = new Date(di.value); d.setDate(d.getDate() + delta);
  di.value = d.toISOString().split("T")[0]; renderHomeworkView();
}

async function renderHomeworkView(forceRebuild = false) {
  const container = document.getElementById("homeworkGroups");
  const date = document.getElementById("homeworkDate").value;
  if (State.groups.length === 0 || State.students.length === 0) {
    container.innerHTML = `<div class="empty-state"><span class="empty-icon">📝</span><p>请先在「班级分组」中导入学生并完成分组</p></div>`;
    _lastHomeworkHash = '';
    return;
  }
  if (!State.homeworkCache[cacheKey(date, State.currentHomeworkTypeId)]) await loadHomeworkForDate(date);
  const records = State.homeworkCache[cacheKey(date, State.currentHomeworkTypeId)] || {};

  // 计算结构哈希（基于分组和学生ID排列）
  let hash = '';
  for (const g of State.groups) {
    hash += g.id + ':';
    const students = State.students.filter(s => s.group_id === g.id);
    hash += students.map(s => s.id).join(',') + ';';
  }

  // 如果结构没变，只更新按钮状态（快速路径，无innerHTML）
  if (!forceRebuild && hash === _lastHomeworkHash && container.children.length > 0) {
    requestAnimationFrame(() => {
      const rows = container.querySelectorAll('.hw-student-row');
      for (const row of rows) {
        const sid = parseInt(row.dataset.studentId);
        const grade = records[sid] ? records[sid].grade : 'X';
        const btns = row.querySelectorAll('.grade-qbtn');
        for (const btn of btns) {
          const isActive = btn.dataset.grade === grade;
          if (isActive !== btn.classList.contains('active')) {
            btn.classList.toggle('active', isActive);
          }
          // 更新 date 属性（日期切换时）
          if (btn.dataset.date !== date) btn.dataset.date = date;
        }
      }
    });
    return;
  }

  // 结构变了，全量重建
  _lastHomeworkHash = hash;
  const groupStudents = {};
  for (const g of State.groups) groupStudents[g.id] = [];
  for (const s of State.students) {
    if (s.group_id && groupStudents[s.group_id]) groupStudents[s.group_id].push(s);
  }

  // 使用 DocumentFragment 减少回流
  const fragment = document.createDocumentFragment();
  const tempDiv = document.createElement('div');

  let html = "";
  for (const g of State.groups) {
    const students = groupStudents[g.id] || [];
    html += `<div class="hw-group-column"><div class="hw-group-header" style="border-left:4px solid ${g.color}"><span class="group-name-dot" style="background:${g.color}"></span>${escapeHtml(g.name)}<span style="margin-left:auto;font-size:.72rem;color:var(--text-lighter)">${students.length}人</span></div><div class="hw-group-students">`;
    for (const s of students) {
      const record = records[s.id];
      const grade = record ? record.grade : "X";
      const zone = getDisplayZone(grade);
      const displayName = formatStudentDisplay(s.name, s.student_code, zone);
      const codeHtml = formatStudentCodeHtml(s.student_code, zone);
      html += `<div class="hw-student-row" data-student-id="${s.id}"><span class="hw-student-name${privacyClass(zone)}">${codeHtml}${escapeHtml(displayName)}</span><div class="grade-quick-select">`;
      for (const gv of ["A","B","C","L","X"]) {
        const gLabel = gradeDisplayLabel(gv);
        const activeClass = gv === grade ? " active" : "";
        html += `<button class="grade-qbtn grade-${gv.toLowerCase()}${activeClass}" data-grade="${gv}" data-sid="${s.id}" data-date="${date}" title="${gLabel}">${gLabel}</button>`;
      }
      html += `</div></div>`;
    }
    html += `</div></div>`;
  }
  tempDiv.innerHTML = html;
  while (tempDiv.firstChild) fragment.appendChild(tempDiv.firstChild);

  container.innerHTML = '';
  container.appendChild(fragment);
  bindGradeButtons();
  // v2: 学生行交错入场
  requestAnimationFrame(() => {
    container.querySelectorAll('.hw-group-students').forEach(g => {
      staggerEntrance(g, '.hw-student-row', 22);
    });
  });
}

/**
 * v1.2 核心优化：即时UI更新
 * 点击等级按钮后立即更新UI，不等API返回
 * API在后台异步发送，失败时回滚
 */
function bindGradeButtons() {
  // 使用全局委托而非逐个绑定
  if (_gradeDelegationBound) return;
  _gradeDelegationBound = true;

  const container = document.getElementById("homeworkGroups");
  container.removeEventListener("click", _gradeClickHandler);
  container.addEventListener("click", _gradeClickHandler);
}

let _gradeDelegationBound = false;
let _lastHomeworkHash = '';     // 跟踪上次渲染的结构哈希，避免不必要的innerHTML重绘

// 防止快速双击同一个按钮
const _pendingGrades = new Map(); // key: "sid-date", value: grade
let _reminderData = [];        // v1.3: 缓存催交数据以便切换显示

async function _gradeClickHandler(e) {
  const btn = e.target.closest(".grade-qbtn");
  if (!btn) return;

  const grade = btn.dataset.grade;
  const sid = parseInt(btn.dataset.sid);
  const date = btn.dataset.date;

  // 如果已经选中，不重复操作
  if (btn.classList.contains("active")) return;

  const key = `${sid}-${date}`;
  // 防止快速重复点击同一学生的同一等级
  if (_pendingGrades.get(key) === grade) return;
  _pendingGrades.set(key, grade);

  // 1. 立即更新UI（即时反馈）
  const row = btn.closest(".hw-student-row");
  if (row) {
    row.querySelectorAll(".grade-qbtn").forEach(b => {
      b.classList.remove("active");
      if (b === btn) {
        b.classList.add("active", "just-set");
        setTimeout(() => b.classList.remove("just-set"), 360);
      }
    });
  }

  // 2. 更新缓存
  const ck = cacheKey(date, State.currentHomeworkTypeId);
  if (!State.homeworkCache[ck]) State.homeworkCache[ck] = {};
  State.homeworkCache[ck][sid] = { student_id: sid, date, grade };

  // 3. 后台发送API（失败回滚）
  try {
    const res = await API.post("/api/homework", { student_id: sid, date, grade, class_id: State.currentClassId, homework_type_id: State.currentHomeworkTypeId });
    if (res.code !== 0) {
      showToast("保存失败: " + res.msg, "error");
      // 回滚缓存
      if (State.homeworkCache[ck]) delete State.homeworkCache[ck][sid];
    }
  } catch (e) {
    showToast("网络错误，请重试", "error");
    if (State.homeworkCache[ck]) delete State.homeworkCache[ck][sid];
  } finally {
    _pendingGrades.delete(key);
  }

  // 4. 防抖刷新统计
  debouncedLoadStats();
}

// 兼容旧版直接调用（保留API）
async function setGradeDirect(studentId, grade, date) {
  // 此函数不再重建整个视图，而是即时更新 + 后台API
  const key = `${studentId}-${date}`;
  _pendingGrades.set(key, grade);

  // 即时更新DOM
  const btn = document.querySelector(`.grade-qbtn[data-sid="${studentId}"][data-grade="${grade}"][data-date="${date}"]`);
  if (btn) {
    const row = btn.closest(".hw-student-row");
    if (row) {
      row.querySelectorAll(".grade-qbtn").forEach(b => {
        b.classList.remove("active");
        if (b === btn) {
          b.classList.add("active", "just-set");
          setTimeout(() => b.classList.remove("just-set"), 360);
        }
      });
    }
  }

  // 更新缓存
  const ck = cacheKey(date, State.currentHomeworkTypeId);
  if (!State.homeworkCache[ck]) State.homeworkCache[ck] = {};
  State.homeworkCache[ck][studentId] = { student_id: studentId, date, grade };

  // 后台API
  try {
    const res = await API.post("/api/homework", { student_id: studentId, date, grade, class_id: State.currentClassId, homework_type_id: State.currentHomeworkTypeId });
    if (res.code !== 0) {
      showToast("登记失败: " + res.msg, "error");
      if (State.homeworkCache[ck]) delete State.homeworkCache[ck][studentId];
    }
  } catch (e) {
    showToast("网络错误", "error");
    if (State.homeworkCache[ck]) delete State.homeworkCache[ck][studentId];
  } finally {
    _pendingGrades.delete(key);
  }

  debouncedLoadStats();
}

// ============================================================
// 催交作业
// ============================================================
function setupReminder() {
  document.getElementById("btnReminder").addEventListener("click", openReminderModal);
  document.getElementById("btnReminderClose").addEventListener("click", () => { closeModal("reminderModal"); });
  document.getElementById("btnCopyReminder").addEventListener("click", copyReminder);
  document.getElementById("btnPrintReminder").addEventListener("click", printReminder);
  document.getElementById("btnExportReminder").addEventListener("click", exportReminder);
  document.getElementById("privacyToggle").addEventListener("change", togglePrivacyMode);
}

async function openReminderModal() {
  const date = document.getElementById("homeworkDate").value;
  const tid = State.currentHomeworkTypeId;
  const res = await API.get(`/api/homework/missing?date=${date}&class_id=${State.currentClassId}&homework_type_id=${tid}`);
  if (res.code !== 0) { showToast("获取数据失败", "error"); return; }
  _reminderData = res.data;
  // 补充学号信息
  _reminderData = _reminderData.map(s => {
    const student = State.students.find(st => st.id === s.student_id);
    return { ...s, student_code: student?.student_code || '' };
  });
  document.getElementById("privacyToggle").checked = reminderShowsCodes();
  document.getElementById("reminderDate").innerHTML = `📅 日期：<strong>${date}</strong> &nbsp;|&nbsp; 未交人数：<strong>${res.total}</strong>`;
  document.getElementById("reminderSummary").textContent = `⚠️ 截至 ${date}，以下 ${res.total} 名学生未交作业，请及时提醒：`;
  renderReminderList();
  document.getElementById("reminderModal").style.display = "";
}

function togglePrivacyMode() {
  const checked = document.getElementById("privacyToggle").checked;
  State.displayMode = checked ? "code" : "name";
  try {
    localStorage.setItem("classtrack_privacy", checked ? "1" : "0");
    localStorage.setItem("classtrack_zone_display", "");
  } catch (e) {}
  updateDisplayModeUI();
  renderReminderList();
  refreshCurrentView();
}

/**
 * 催交名单当前是否显示学号：显式「仅显示学号」，或「分区显示」模式下
 * （催交名单全是未交学生，属于未完成分区，自动保护隐私）
 */
function reminderShowsCodes() {
  return State.displayMode === "code" || State.displayMode === "auto";
}

function renderReminderList() {
  const byGroup = {};
  const showCodes = reminderShowsCodes();
  for (const s of _reminderData) {
    const gname = s.group_name || "未分组";
    if (!byGroup[gname]) byGroup[gname] = [];
    const displayName = showCodes ? (s.student_code || s.student_name) : s.student_name;
    byGroup[gname].push(displayName);
  }
  let listHtml = "";
  const pClass = showCodes ? ' privacy' : '';
  for (const [gname, entries] of Object.entries(byGroup)) {
    listHtml += `<div class="reminder-group${pClass}"><strong>📌 ${escapeHtml(gname)}：</strong>${entries.map(n => escapeHtml(n)).join("、")}</div>`;
  }
  if (!listHtml) listHtml = `<div style="color:var(--green);font-weight:600;">🎉 太棒了！所有学生都已交作业！</div>`;
  document.getElementById("reminderList").innerHTML = listHtml;
}

function getReminderText() {
  const date = document.getElementById("homeworkDate").value;
  const byGroup = {};
  const showCodes = reminderShowsCodes();
  for (const s of _reminderData) {
    const gname = s.group_name || "未分组";
    if (!byGroup[gname]) byGroup[gname] = [];
    const displayName = showCodes ? (s.student_code || s.student_name) : s.student_name;
    byGroup[gname].push(displayName);
  }
  let text = `【催交通知】${date}\n`;
  for (const [gname, entries] of Object.entries(byGroup)) {
    text += `📌 ${gname}：${entries.join("、")}\n`;
  }
  text += `\n请以上同学尽快补交作业！`;
  return text;
}

async function copyReminder() {
  try {
    await navigator.clipboard.writeText(getReminderText());
    showToast("已复制到剪贴板，可直接粘贴到家长群", "success");
  } catch (e) { showToast("复制失败，请手动选择复制", "error"); }
}

function printReminder() {
  const w = window.open("", "_blank", "width=650,height=500");
  const isPrivacy = reminderShowsCodes();
  const privacyTitle = isPrivacy ? '（仅显示学号）' : '';
  w.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>催交通知单</title>
    <style>body{font-family:"Microsoft YaHei",sans-serif;padding:30px;line-height:2.2;font-size:15px}
    h2{color:#E8A0BF} .date{color:#999} .group{margin:8px 0}
    .privacy{font-family:"SF Mono",Consolas,monospace;letter-spacing:1px}
    @media print{body{padding:20px}}</style></head>
    <body><h2>🔔 催交通知单${privacyTitle}</h2><p class="date">日期：${document.getElementById("homeworkDate").value}</p>
    ${document.getElementById("reminderList").innerHTML}
    <p style="margin-top:20px;color:#999">—— ClassTrack 班级作业管理</p></body></html>`);
  w.document.close(); setTimeout(() => w.print(), 500);
}

function exportReminder() {
  window.open(`/api/export/class?class_id=${State.currentClassId}&start=${document.getElementById("homeworkDate").value}&end=${document.getElementById("homeworkDate").value}`, "_blank");
}

// ============================================================
// 报表导出
// ============================================================
function setupExportControls() {
  document.getElementById("btnQueryRecords").addEventListener("click", queryRecords);
  document.getElementById("btnExportStudent").addEventListener("click", exportStudent);
  document.getElementById("btnExportClass").addEventListener("click", exportClass);
}

async function prepareExportTab() {
  const end = new Date(); const start = new Date(); start.setDate(start.getDate() - 30);
  document.getElementById("exportStartDate").value = start.toISOString().split("T")[0];
  document.getElementById("exportEndDate").value = end.toISOString().split("T")[0];
  const sel = document.getElementById("exportStudentSelect");
  sel.innerHTML = '<option value="">-- 请选择学生 --</option>';
  for (const s of State.students) {
    const displayName = formatStudentDisplay(s.name, s.student_code);
    const codeLabel = (State.displayMode !== "code" && s.student_code) ? `[${s.student_code}] ` : '';
    sel.innerHTML += `<option value="${s.id}">${codeLabel}${escapeHtml(displayName)}${s.group_name ? ` [${escapeHtml(s.group_name)}]` : ""}</option>`;
  }
}

async function queryRecords() {
  const start = document.getElementById("exportStartDate").value;
  const end = document.getElementById("exportEndDate").value;
  if (!start || !end) { showToast("请选择日期范围", "error"); return; }
  if (start > end) { showToast("起始日期不能晚于结束日期", "error"); return; }
  const tid = State.currentHomeworkTypeId;
  const res = await API.get(`/api/homework/range?class_id=${State.currentClassId}&start=${start}&end=${end}&homework_type_id=${tid}`);
  if (res.code === 0) { document.getElementById("resultCount").textContent = res.total || 0; renderPreviewTable(res.data || []); }
}

function renderPreviewTable(records) {
  const card = document.getElementById("previewCard");
  const tbody = document.getElementById("previewTbody");
  const count = document.getElementById("previewCount");
  if (records.length === 0) { card.style.display = "none"; return; }
  card.style.display = ""; count.textContent = `共 ${records.length} 条`;
  const codeMap = {};
  State.students.forEach(s => { codeMap[s.id] = s.student_code || ""; });
  tbody.innerHTML = records.slice(0, 200).map(r => {
    const code = codeMap[r.student_id] || "";
    const displayName = formatStudentDisplay(r.student_name, code);
    const isCode = State.displayMode === "code";
    return `<tr><td class="${isCode ? 'privacy-mode' : ''}" style="${isCode ? 'font-family:monospace;letter-spacing:1px' : ''}">${escapeHtml(displayName)}</td><td>${escapeHtml(r.group_name)}</td><td>${r.date}</td><td class="grade-cell-${r.grade.toLowerCase()}">${r.grade_label}</td></tr>`;
  }).join("");
  if (records.length > 200) tbody.innerHTML += `<tr><td colspan="4" style="text-align:center;color:var(--text-lighter)">仅显示前200条，完整数据请导出Excel</td></tr>`;
}

function exportStudent() {
  const sid = document.getElementById("exportStudentSelect").value;
  const start = document.getElementById("exportStartDate").value;
  const end = document.getElementById("exportEndDate").value;
  if (!sid) { showToast("请选择学生", "error"); return; }
  window.open(`/api/export/student/${sid}?class_id=${State.currentClassId}&start=${start}&end=${end}`, "_blank");
}

function exportClass() {
  const start = document.getElementById("exportStartDate").value;
  const end = document.getElementById("exportEndDate").value;
  window.open(`/api/export/class?class_id=${State.currentClassId}&start=${start}&end=${end}`, "_blank");
}

// ============================================================
// 数据分析 - Tab 4
// ============================================================
let chartPie = null, chartBar = null, chartLine = null;
let _lastChartDataHash = '';  // v2: 缓存图表数据哈希，避免无意义销毁重建

function setupAnalyticsControls() {
  document.getElementById("btnAnalyticsPrev").addEventListener("click", () => { shiftAnalyticsDate(-1); });
  document.getElementById("btnAnalyticsNext").addEventListener("click", () => { shiftAnalyticsDate(1); });
  document.getElementById("btnAnalyticsToday").addEventListener("click", () => { setAnalyticsToday(); loadAnalytics(); });
  document.getElementById("analyticsDate").addEventListener("change", () => loadAnalytics());

  // 绑定到父容器（统计卡片可能重绘）
  const cardsContainer = document.getElementById("statsCards");
  if (cardsContainer) {
    cardsContainer.addEventListener("click", (e) => {
      const card = e.target.closest("[data-detail]");
      if (card) openDetailModal(card.dataset.detail);
    });
  }

  document.getElementById("btnDetailClose").addEventListener("click", () => closeModal("detailModal"));
  document.getElementById("btnReportClose").addEventListener("click", () => closeModal("studentReportModal"));
  document.getElementById("btnExportStudentReport").addEventListener("click", exportStudentReport);
}

function setAnalyticsToday() {
  document.getElementById("analyticsDate").value = new Date().toISOString().split("T")[0];
}

function shiftAnalyticsDate(delta) {
  const di = document.getElementById("analyticsDate");
  const d = new Date(di.value); d.setDate(d.getDate() + delta);
  di.value = d.toISOString().split("T")[0]; loadAnalytics();
}

async function loadAnalytics() {
  const date = document.getElementById("analyticsDate").value;
  const cid = State.currentClassId;

  const tid = State.currentHomeworkTypeId || 0;
  const [overview, trend, ranking, trendCompare, alerts] = await Promise.all([
    API.get(`/api/analytics/overview?date=${date}&class_id=${cid}&homework_type_id=${tid}`),
    API.get(`/api/analytics/trend?days=14&class_id=${cid}&homework_type_id=${tid}`),
    API.get(`/api/analytics/group-ranking?date=${date}&class_id=${cid}&homework_type_id=${tid}`),
    API.get(`/api/analytics/trend-compare?period=week&class_id=${cid}&homework_type_id=${tid}`),
    API.get(`/api/analytics/student-alerts?days=14&class_id=${cid}&homework_type_id=${tid}`),
  ]);

  if (overview.code !== 0) return;
  const d = overview.data;
  document.getElementById("analyticsClassInfo").textContent =
    `班级：${State.classes.find(c => c.id === State.currentClassId)?.name || ""}`;

  const total = d.total_students;
  const submitted = (d.grade_counts.A || 0) + (d.grade_counts.B || 0) + (d.grade_counts.C || 0);
  const missing = (d.grade_counts.X || 0) + (d.unrecorded || 0);
  const aRate = total > 0 ? Math.round((d.grade_counts.A || 0) / total * 100) : 0;
  const bRate = total > 0 ? Math.round((d.grade_counts.B || 0) / total * 100) : 0;
  const cRate = total > 0 ? Math.round((d.grade_counts.C || 0) / total * 100) : 0;
  const submitRate = total > 0 ? Math.round(submitted / total * 100) : 0;
  const avgScore = submitted > 0 ? (((d.grade_counts.A||0)*3 + (d.grade_counts.B||0)*2 + (d.grade_counts.C||0)*1) / submitted).toFixed(1) : "0.0";

  // 7个统计卡片 — v2: 使用带动画的数值
  animateValue("scTotal", total);
  animateValue("scSubmitted", submitRate, { suffix: "%" });
  animateValue("scARate", aRate, { suffix: "%" });
  animateValue("scBRate", bRate, { suffix: "%" });
  animateValue("scCRate", cRate, { suffix: "%" });
  animateValue("scMissing", missing);
  document.getElementById("scAvgScore").textContent = avgScore;

  // 饼图 — v2: 数据哈希比较避免无意义重建
  const leave = d.grade_counts.L || 0;
  const pieData = [d.grade_counts.A || 0, d.grade_counts.B || 0, d.grade_counts.C || 0, leave, missing];
  const gc = d.group_comparison || [];
  const chartHash = pieData.join(',') + '|' + gc.map(g => g.a_rate + '-' + g.missing).join(',');
  const needsRebuild = chartHash !== _lastChartDataHash;
  _lastChartDataHash = chartHash;

  const chartBodyEl = document.querySelector('.charts-grid');
  if (chartBodyEl && needsRebuild) {
    chartBodyEl.style.opacity = '0.6';
    chartBodyEl.style.transition = 'opacity 0.5s var(--glass-spring)';
  }

  const pieCtx = document.getElementById("chartPie").getContext("2d");
  if (chartPie) chartPie.destroy();
  chartPie = new Chart(pieCtx, {
    type: "doughnut",
    data: {
      labels: ["A (优秀)", "B (良好)", "C (待提升)", "请假", "未交"],
      datasets: [{
        data: pieData,
        backgroundColor: ["#A8D5BA", "#7EB5D6", "#F4C97E", "#C5B3E6", "#E8A0BF"],
        borderWidth: 2, borderColor: "#fff",
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 600, easing: 'easeOutCubic' },
      plugins: {
        legend: { position: "bottom", labels: { padding: 16, font: { size: 13, family: "'Microsoft YaHei',sans-serif" }, usePointStyle: true, pointStyleWidth: 10 } }
      }
    }
  });

  // 分组柱状图
  const barCtx = document.getElementById("chartBar").getContext("2d");
  if (chartBar) chartBar.destroy();
  chartBar = new Chart(barCtx, {
    type: "bar",
    data: {
      labels: gc.map(g => g.group_name),
      datasets: [
        { label: "A率 (%)", data: gc.map(g => g.a_rate), backgroundColor: "#A8D5BA", borderRadius: 8 },
        { label: "未交人数", data: gc.map(g => g.missing), backgroundColor: "#E8A0BF", borderRadius: 8 },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 600, easing: 'easeOutCubic' },
      scales: { y: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.04)" }, ticks: { font: { size: 11 } } }, x: { ticks: { font: { size: 11 } } } },
      plugins: { legend: { position: "bottom", labels: { font: { size: 12 }, usePointStyle: true } } }
    }
  });

  // 趋势折线图
  const lineCtx = document.getElementById("chartLine")?.getContext("2d");
  if (lineCtx) {
    if (chartLine) chartLine.destroy();
    const td = trend.data || [];
    chartLine = new Chart(lineCtx, {
      type: "line",
      data: {
        labels: td.map(t => t.date.slice(5)),
        datasets: [{
          label: "提交率 (%)", data: td.map(t => t.rate),
          borderColor: "#7EB5D6", backgroundColor: "rgba(126,181,214,0.1)",
          fill: true, tension: 0.4, pointRadius: 4, pointBackgroundColor: "#7EB5D6",
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: 600, easing: 'easeOutCubic' },
        scales: {
          y: { min: 0, max: 100, grid: { color: "rgba(0,0,0,0.04)" }, ticks: { callback: v => v + "%", font: { size: 11 } } },
          x: { ticks: { font: { size: 10 } } }
        },
        plugins: { legend: { display: false } }
      }
    });
  }

  // v2: 图表渲染完成后恢复透明度
  if (chartBodyEl && needsRebuild) {
    setTimeout(() => {
      chartBodyEl.style.opacity = '1';
    }, 400);
  }

  // 环比趋势图
  renderTrendCompare(trendCompare.data);
  // 小组排行榜
  renderGroupRanking(ranking.data, ranking.date);
  // 学生预警
  renderStudentAlerts(alerts.data);
}

// v2: 数值平滑动画（支持小数、后缀）
function animateValue(id, target, options = {}) {
  const { duration = 350, suffix = '', decimals = 0 } = options;
  const el = document.getElementById(id);
  if (!el) return;
  const rawText = el.textContent || '0';
  const current = parseFloat(rawText.replace(/[^0-9.]/g, '')) || 0;
  if (isNaN(current) || isNaN(target)) { el.textContent = target + suffix; return; }
  if (current === target) { el.textContent = (decimals > 0 ? target.toFixed(decimals) : target) + suffix; return; }
  const start = performance.now();
  function step(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
    const val = current + (target - current) * eased;
    el.textContent = (decimals > 0 ? val.toFixed(decimals) : Math.round(val)) + suffix;
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ============================================================
// 数据概览渲染函数
// ============================================================
let chartCompare = null;

function renderTrendCompare(data) {
  if (!data) return;
  const ctx = document.getElementById("chartCompare")?.getContext("2d");
  if (!ctx) return;
  if (chartCompare) chartCompare.destroy();
  chartCompare = new Chart(ctx, {
    type: "line",
    data: {
      labels: data.current.map(d => d.date),
      datasets: [
        {
          label: "本期", data: data.current.map(d => d.rate),
          borderColor: "#7EB5D6", backgroundColor: "rgba(126,181,214,0.08)",
          fill: true, tension: 0.4, pointRadius: 3, borderWidth: 2,
        },
        {
          label: "上期", data: data.previous.map(d => d.rate),
          borderColor: "#BFBBBB", backgroundColor: "transparent",
          borderDash: [5, 3], tension: 0.4, pointRadius: 2, borderWidth: 1.5,
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 600, easing: 'easeOutCubic' },
      scales: {
        y: { min: 0, max: 100, grid: { color: "rgba(0,0,0,0.04)" }, ticks: { callback: v => v + "%", font: { size: 10 } } },
        x: { ticks: { font: { size: 9 } } }
      },
      plugins: {
        legend: { position: "bottom", labels: { font: { size: 11 }, usePointStyle: true, padding: 12 } }
      }
    }
  });
  const changeEl = document.getElementById("compareSummary");
  if (changeEl) {
    const arrow = data.change >= 0 ? "↑" : "↓";
    const color = data.change >= 0 ? "var(--green)" : "var(--pink)";
    changeEl.innerHTML = `本期平均 <strong>${data.current_avg}%</strong> | 上期 <strong>${data.previous_avg}%</strong> | 变化 <strong style="color:${color}">${arrow} ${Math.abs(data.change)}%</strong>`;
  }
}

function renderGroupRanking(ranking, date) {
  const body = document.getElementById("rankingBody");
  const dateEl = document.getElementById("rankingDate");
  if (dateEl) dateEl.textContent = date;
  if (!body) return;
  if (!ranking || ranking.length === 0) {
    body.innerHTML = '<div style="text-align:center;color:var(--text-lighter);padding:20px">暂无分组数据</div>';
    return;
  }
  const medals = ["🥇", "🥈", "🥉"];
  body.innerHTML = ranking.map((g, i) => `
    <div class="ranking-item">
      <span class="ranking-medal">${i < 3 ? medals[i] : (i + 1)}</span>
      <span class="ranking-name">${escapeHtml(g.group_name)}</span>
      <div class="ranking-bar-wrap">
        <div class="ranking-bar-fill" style="background:${g.color}" data-target-width="${g.a_rate}">
        </div>
        <span class="ranking-bar-label">${g.a_rate}%</span>
      </div>
      <span class="ranking-stats">提交率 ${g.submit_rate}% · ${g.total}人</span>
    </div>
  `).join('');
  // v2: 触发条形图入场动画 — 使用 scaleX 走 GPU 合成
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      body.querySelectorAll('.ranking-bar-fill').forEach(bar => {
        const target = bar.dataset.targetWidth;
        if (target) {
          bar.style.transform = `scaleX(${parseFloat(target) / 100})`;
        }
      });
    });
  });
}

function renderStudentAlerts(data) {
  const body = document.getElementById("alertsBody");
  if (!body) return;
  if (!data || (data.at_risk.length === 0 && data.improving.length === 0)) {
    body.innerHTML = '<div class="alerts-empty">🎉 目前没有需要特别关注的学生</div>';
    return;
  }
  // 构建学号查找表（API可能不返回student_code）
  const codeMap = {};
  State.students.forEach(s => { codeMap[s.id] = s.student_code || ""; });
  const getDisplay = (s, zone) => formatStudentDisplay(s.student_name, codeMap[s.student_id] || "", zone);
  let html = '<div class="alerts-tabs">';
  html += `<button class="alerts-tab-btn tab-risk active" data-alerts-tab="risk">⚠️ 需关注 (${data.at_risk.length})</button>`;
  html += `<button class="alerts-tab-btn tab-improve" data-alerts-tab="improve">🌟 进步中 (${data.improving.length})</button>`;
  html += '</div>';
  html += '<div class="alerts-panel" id="alertsRiskPanel">';
  if (data.at_risk.length === 0) {
    html += '<div class="alerts-empty">✅ 暂无连续未交的学生</div>';
  } else {
    const riskZone = 'incomplete';  // 需关注的学生 → 显示学号
    html += data.at_risk.map(s => {
      const displayName = getDisplay(s, riskZone);
      return `
      <div class="alert-student-item risk" data-sid="${s.student_id}" data-sname="${escapeHtml(displayName)}">
        <span class="alert-student-name${privacyClass(riskZone)}">${escapeHtml(displayName)}</span>
        <span class="alert-student-group">${escapeHtml(s.group_name)}</span>
        <span class="alert-student-tag risk">连续${s.consecutive_x}次未交</span>
        <span class="alert-student-grades">${s.last_grades.map(g => `<span class="g-${g}">${gradeDisplayLabel(g)}</span>`).join('')}</span>
      </div>`;
    }).join('');
  }
  html += '</div>';
  html += '<div class="alerts-panel" id="alertsImprovePanel" style="display:none">';
  if (data.improving.length === 0) {
    html += '<div class="alerts-empty">💪 暂未检测到明显进步趋势</div>';
  } else {
    const improveZone = 'completed';  // 进步中的学生 → 显示姓名
    html += data.improving.map(s => {
      const displayName = getDisplay(s, improveZone);
      return `
      <div class="alert-student-item improve" data-sid="${s.student_id}" data-sname="${escapeHtml(displayName)}">
        <span class="alert-student-name${privacyClass(improveZone)}">${escapeHtml(displayName)}</span>
        <span class="alert-student-group">${escapeHtml(s.group_name)}</span>
        <span class="alert-student-tag improve">${s.from_grade}→${s.to_grade} 进步</span>
        <span class="alert-student-grades">${s.recent_grades.map(g => `<span class="g-${g}">${gradeDisplayLabel(g)}</span>`).join('')}</span>
      </div>`;
    }).join('');
  }
  html += '</div>';
  body.innerHTML = html;

  // 预警子Tab切换
  body.querySelectorAll('.alerts-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      body.querySelectorAll('.alerts-tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('alertsRiskPanel').style.display = btn.dataset.alertsTab === 'risk' ? '' : 'none';
      document.getElementById('alertsImprovePanel').style.display = btn.dataset.alertsTab === 'improve' ? '' : 'none';
    });
  });

  // 点击学生打开个人报表
  body.querySelectorAll('.alert-student-item').forEach(item => {
    item.addEventListener('click', () => {
      openStudentReport(parseInt(item.dataset.sid), item.dataset.sname);
    });
  });
}

// 环比周期切换
document.body.addEventListener('click', function(e) {
  const btn = e.target.closest('.compare-period-btn');
  if (!btn) return;
  document.querySelectorAll('.compare-period-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const period = btn.dataset.period;
  const date = document.getElementById('analyticsDate').value;
  API.get(`/api/analytics/trend-compare?period=${period}&class_id=${State.currentClassId}&homework_type_id=${State.currentHomeworkTypeId || 0}`).then(res => {
    if (res.code === 0) renderTrendCompare(res.data);
  });
});

// ============================================================
// 扫码登记系统 (Tab 5)
// ============================================================
let pcScanner = null;           // ClassTrackScanner 实例
let pcScanning = false;
let currentScanGrade = "A";
let currentScanMode = "batch";
let pcScanBuffer = [];           // PC 批量预览缓冲
let pendingScans = [];
let mobilePollTimer = null;
let mobileLastScanTs = new Date().toISOString().replace("T", " ").slice(0, 19); // 当前时间，不加载历史数据
let mobileScanGrade = "A";

document.body.addEventListener("click", function (e) {
  const gbtn = e.target.closest(".grade-preset-btn");
  if (!gbtn) return;
  const grade = gbtn.dataset.grade;
  const device = gbtn.dataset.device || "pc";
  if (device === "pc") {
    currentScanGrade = grade;
    document.querySelectorAll("#batchGradeRow .grade-preset-btn").forEach(b => b.classList.remove("active"));
    gbtn.classList.add("active");
  } else if (device === "mobile") {
    mobileScanGrade = grade;
    document.querySelectorAll("#mobileScanPanel .grade-preset-btn").forEach(b => b.classList.remove("active"));
    gbtn.classList.add("active");
  }
});

document.body.addEventListener("click", function (e) {
  const sbtn = e.target.closest(".scan-type-btn");
  if (!sbtn) return;
  document.querySelectorAll(".scan-type-btn").forEach(b => b.classList.remove("active"));
  sbtn.classList.add("active");
  currentScanMode = sbtn.dataset.scanType;
  document.getElementById("batchGradeRow").style.display = currentScanMode === "batch" ? "" : "none";
});

document.getElementById("btnStartPcScan").addEventListener("click", startPcScan);
document.getElementById("btnStopPcScan").addEventListener("click", stopPcScan);

async function startPcScan() {
  try {
    // 创建 ClassTrackScanner 实例（BarcodeDetector 硬件加速 + zxing-wasm 兜底）
    pcScanner = new ClassTrackScanner({
      fps: 30,
      facingMode: "environment",
      onScan: onPcCodesDetected,
    });
    const engine = await pcScanner.init();
    const engineLabel = engine === "barcode-detector" ? "硬件加速" : "WASM 软件";

    // 注入 video 元素
    const container = document.getElementById("pcReader");
    container.innerHTML = "";
    const video = document.createElement("video");
    video.id = "pcScanVideo";
    video.style.width = "100%";
    video.style.borderRadius = "8px";
    video.setAttribute("playsinline", "");
    video.setAttribute("autoplay", "");
    container.appendChild(video);

    document.getElementById("btnStartPcScan").style.display = "none";
    document.getElementById("btnStopPcScan").style.display = "";

    await pcScanner.start(video);
    pcScanning = true;
    showToast(`PC 扫码已启动（${engineLabel}）`, "info");
  } catch (err) {
    showToast("摄像头启动失败: " + err.message, "error");
    document.getElementById("btnStartPcScan").style.display = "";
    document.getElementById("btnStopPcScan").style.display = "none";
  }
}

async function stopPcScan() {
  if (pcScanner && pcScanning) {
    await pcScanner.stop();
    pcScanning = false;
    pcScanner = null;
  }
  document.getElementById("btnStartPcScan").style.display = "";
  document.getElementById("btnStopPcScan").style.display = "none";
  showToast("扫码已停止", "info");
}

/**
 * ★ 一帧多码回调：同一帧画面中识别到的所有新学号（已去重）
 * @param {string[]} codes
 */
async function onPcCodesDetected(codes) {
  if (!pcScanning || codes.length === 0) return;

  // 批量查询所有学号对应的学生信息
  const cid = State.currentClassId;
  const grade = currentScanMode === "batch" ? currentScanGrade : null;

  for (const code of codes) {
    try {
      const res = await API.get(`/api/student/by-code/${encodeURIComponent(code)}?class_id=${cid}`);
      if (res.code === 0) {
        const s = res.data;
        const displayName = formatStudentDisplay(s.name, s.student_code);

        if (currentScanMode === "single") {
          const chosen = prompt(
            `学生：${displayName}${State.displayMode !== "code" && s.student_code ? ` (${s.student_code})` : ""}\n请输入等级 (A/B/C/X，L=请假)：`,
            "A"
          );
          if (chosen && ["A","B","C","L","X"].includes(chosen.toUpperCase())) {
            await API.post("/api/scan/single", {
              student_code: code,
              grade: chosen.toUpperCase(),
              date: document.getElementById("homeworkDate").value,
              class_id: State.currentClassId,
              homework_type_id: State.currentHomeworkTypeId,
            });
            showToast(`${displayName} → ${chosen.toUpperCase()}`, "success");
          }
        } else {
          addPendingScan(code, displayName, grade, s.id, false);
          showToast(`${displayName} → ${gradeDisplayLabel(grade)}`, "info");
        }
      } else if (res.external) {
        addPendingScan(code, "未知学生", currentScanGrade, null, true);
        showToast(`未找到学号 ${code}，可能非本班学生`, "error");
      }
    } catch (e) {
      showToast("识别失败", "error");
    }
  }

  // 单次模式扫完后自动刷新统计
  if (currentScanMode === "single") debouncedLoadStats();
}

function addPendingScan(code, name, grade, studentId, external) {
  pendingScans = pendingScans.filter(p => p.student_code !== code);
  pendingScans.push({ student_code: code, student_name: name, grade, student_id: studentId, external });
  renderPendingList();
}

function renderPendingList() {
  const list = document.getElementById("pendingList");
  document.getElementById("pendingCount").textContent = `${pendingScans.length}条`;
  if (pendingScans.length === 0) {
    list.innerHTML = '<div style="text-align:center;color:var(--text-lighter);padding:20px">扫码后学生将显示在这里</div>';
    return;
  }
  list.innerHTML = pendingScans.map((p, i) => {
    const displayName = formatStudentDisplay(p.student_name, p.student_code);
    return `
    <div class="pending-item ${p.external ? 'external' : ''}">
      <span class="pi-code">${formatStudentCodeHtml(p.student_code)}</span>
      <span class="pi-name${privacyClass()}">${escapeHtml(displayName)}</span>
      ${p.external ? '<span class="pi-external">⚠ 非本班</span>' : ''}
      <span class="pi-grade grade-${(p.grade||'x').toLowerCase()}">${gradeDisplayLabel(p.grade)}</span>
      <button class="pi-del" data-idx="${i}">✕</button>
    </div>`;
  }).join("");
  list.querySelectorAll(".pi-del").forEach(btn => {
    btn.addEventListener("click", function () {
      const idx = parseInt(this.dataset.idx);
      pendingScans.splice(idx, 1);
      renderPendingList();
    });
  });
}

document.getElementById("btnConfirmScans").addEventListener("click", async () => {
  if (pendingScans.length === 0) { showToast("没有待保存的记录", "error"); return; }
  const valid = pendingScans.filter(p => !p.external && p.student_id);
  if (valid.length === 0) { showToast("没有有效记录可保存", "error"); return; }
  const res = await API.post("/api/scan/batch", {
    date: document.getElementById("homeworkDate").value,
    records: valid.map(p => ({ student_code: p.student_code, grade: p.grade })),
    class_id: State.currentClassId,
    homework_type_id: State.currentHomeworkTypeId
  });
  if (res.code === 0) {
    showToast(res.msg, "success");
    pendingScans = [];
    renderPendingList();
    State.homeworkCache = {};
    await loadStats();
    if (State.activeTab === "analytics") loadAnalytics();
    if (State.activeTab === "homework") renderHomeworkView();
  }
});

document.getElementById("btnClearPending").addEventListener("click", () => {
  pendingScans = [];
  renderPendingList();
});

// ---- 手机联动 ----
document.getElementById("btnGenPairQR").addEventListener("click", async () => {
  const res = await API.get("/api/mobile/pair");
  if (res.code === 0) {
    const url = res.data.url;
    document.getElementById("mobileUrl").textContent = url;
    document.getElementById("mobileStatus").textContent = "🟢 等待手机连接...";
    document.getElementById("mobileStatus").className = "mobile-status";
    const box = document.getElementById("pairQRBox");
    box.style.display = "";
    // 使用服务端生成的真实二维码图片（离线可用，无需 CDN）
    // 使用 query 参数避免 URL 中的特殊字符导致路由匹配失败
    box.innerHTML = `<img src="/api/qrcode?data=${encodeURIComponent(url)}&size=160"
      width="150" height="150" alt="配对二维码"
      style="display:block;border-radius:12px">`;
    showToast("配对二维码已生成，手机扫码即可接入", "success");
    startMobilePolling();
  }
});

function startMobilePolling() {
  if (mobilePollTimer) return;
  document.getElementById("mobileStatus").textContent = "🟢 监听中...";
  mobilePollTimer = setInterval(pollMobileScans, 500);
}

function stopMobilePolling() {
  if (mobilePollTimer) { clearInterval(mobilePollTimer); mobilePollTimer = null; }
}

async function pollMobileScans() {
  try {
    // ★ nocache: 轮询必须绕过缓存，否则 30 秒内都返回旧数据
    const res = await API.get(`/api/mobile/scans?since=${encodeURIComponent(mobileLastScanTs)}&class_id=${State.currentClassId}`, { nocache: true });
    if (res.code === 0 && res.data.length > 0) {
      mobileLastScanTs = res.since;
      document.getElementById("mobileStatus").textContent = `🟢 已连接 · ${res.data.length} 条新记录`;
      document.getElementById("mobileScanCount").textContent = `本次: ${res.data.length} 条`;
      for (const s of res.data) {
        const grade = mobileScanGrade;
        addPendingScan(s.student_code, s.student_name, grade, s.student_id, !s.found);
      }
    }
  } catch (e) { /* ignore polling errors */ }
}

document.getElementById("btnRefreshMobile").addEventListener("click", () => {
  mobileLastScanTs = new Date().toISOString().replace("T", " ").slice(0, 19);
  pollMobileScans();
});
document.getElementById("btnClearMobile").addEventListener("click", async () => {
  await API.post("/api/mobile/clear");
  mobileLastScanTs = new Date().toISOString().replace("T", " ").slice(0, 19);
  showToast("已清空手机扫码记录", "info");
});

// 作业登记子Tab按钮事件委托
document.body.addEventListener('click', function(e) {
  const btn = e.target.closest('.hw-subtab-btn');
  if (btn) switchHWSubtab(btn.dataset.hwSubtab);
});

// ============================================================
// 数据概览详情弹窗 & 学生报表
// ============================================================
let _currentReportSid = null;
let _currentReportName = "";

async function openDetailModal(type) {
  const date = document.getElementById("analyticsDate").value;
  const modal = document.getElementById("detailModal");
  const title = document.getElementById("detailModalTitle");
  const summary = document.getElementById("detailSummary");
  const list = document.getElementById("detailList");

  if (type === "all") {
    title.textContent = "👨‍🎓 班级全部学生";
    summary.innerHTML = `共 <strong>${State.students.length}</strong> 名学生`;
    list.innerHTML = State.students.map(s => {
      const gname = s.group_name || "未分组";
      const gcolor = s.group_color || "";
      const displayName = formatStudentDisplay(s.name, s.student_code);
      const codeLabel = formatStudentCodeHtml(s.student_code);
      return `<div class="detail-item" data-sid="${s.id}" data-sname="${escapeHtml(displayName)}" style="cursor:pointer;">
        <span class="detail-name${privacyClass()}">${codeLabel}${escapeHtml(displayName)}</span>
        <span class="detail-group" style="${gcolor ? 'background:'+gcolor+';color:white;padding:2px 8px;border-radius:10px;font-size:.72rem' : ''}">${escapeHtml(gname)}</span>
      </div>`;
    }).join("");
    list.querySelectorAll(".detail-item").forEach(item => {
      item.addEventListener("click", () => {
        const sid = parseInt(item.dataset.sid);
        const sname = item.dataset.sname;
        openStudentReport(sid, sname);
      });
    });
  } else if (type === "submitted") {
    title.textContent = "✅ 今日已交学生";
    const zone = 'completed';  // 已交学生 → 显示姓名
    const res = await API.get(`/api/analytics/submitted?date=${date}&class_id=${State.currentClassId}&homework_type_id=${State.currentHomeworkTypeId || 0}`);
    if (res.code === 0) {
      summary.innerHTML = `日期：<strong>${date}</strong> &nbsp;|&nbsp; 已交：<strong>${res.total}</strong> 人`;
      list.innerHTML = res.data.map(s => {
        const code = s.student_code || "";
        const displayName = formatStudentDisplay(s.student_name, code, zone);
        return `
        <div class="detail-item" data-sid="${s.student_id}" data-sname="${escapeHtml(displayName)}" style="cursor:pointer;">
          <span class="detail-name${privacyClass(zone)}">${formatStudentCodeHtml(code, zone)}${escapeHtml(displayName)}</span>
          <span class="detail-group">${escapeHtml(s.group_name)}</span>
          <span class="grade-badge grade-${s.grade.toLowerCase()}" style="font-size:.7rem;width:28px;height:22px;">${s.grade_label}</span>
        </div>`;
      }).join("");
      list.querySelectorAll(".detail-item").forEach(item => {
        item.addEventListener("click", () => {
          openStudentReport(parseInt(item.dataset.sid), item.dataset.sname);
        });
      });
    }
  } else if (type === "missing") {
    title.textContent = "⚠️ 今日未交学生";
    const zone = 'incomplete';  // 未交学生 → 显示学号
    const res = await API.get(`/api/analytics/missing?date=${date}&class_id=${State.currentClassId}&homework_type_id=${State.currentHomeworkTypeId || 0}`);
    if (res.code === 0) {
      summary.innerHTML = `日期：<strong>${date}</strong> &nbsp;|&nbsp; 未交：<strong>${res.total}</strong> 人`;
      if (res.data.length === 0) {
        list.innerHTML = `<div style="text-align:center;padding:20px;color:var(--green);font-weight:600;">🎉 太棒了！所有学生都已交作业！</div>`;
      } else {
        list.innerHTML = res.data.map(s => {
          const code = s.student_code || "";
          const displayName = formatStudentDisplay(s.student_name, code, zone);
          return `
          <div class="detail-item" data-sid="${s.student_id}" data-sname="${escapeHtml(displayName)}" style="cursor:pointer;">
            <span class="detail-name${privacyClass(zone)}">${formatStudentCodeHtml(code, zone)}${escapeHtml(displayName)}</span>
            <span class="detail-group">${escapeHtml(s.group_name)}</span>
          </div>`;
        }).join("");
        list.querySelectorAll(".detail-item").forEach(item => {
          item.addEventListener("click", () => {
            openStudentReport(parseInt(item.dataset.sid), item.dataset.sname);
          });
        });
      }
    }
  } else if (type === "arate" || type === "brate" || type === "crate") {
    const grade = type.charAt(0).toUpperCase(); // "A", "B", "C"
    const gradeLabels = { A: "⭐ A率详情", B: "🔵 B率详情", C: "🟡 C率详情" };
    const gradeEmoji = { A: "🏆", B: "🥈", C: "📝" };
    const zone = 'completed';  // A/B/C 学生 → 显示姓名
    title.textContent = gradeLabels[grade];
    const res = await API.get(`/api/analytics/submitted?date=${date}&class_id=${State.currentClassId}&grade=${grade}&homework_type_id=${State.currentHomeworkTypeId || 0}`);
    if (res.code === 0) {
      const gradeCount = res.total;
      const overview = await API.get(`/api/analytics/overview?date=${date}&class_id=${State.currentClassId}&homework_type_id=${State.currentHomeworkTypeId || 0}`);
      const total = overview.code === 0 ? overview.data.total_students : 0;
      const rate = total > 0 ? Math.round(gradeCount / total * 100) : 0;
      summary.innerHTML = `日期：<strong>${date}</strong> &nbsp;|&nbsp; ${grade}率：<strong>${rate}%</strong>（${gradeCount}/${total}）`;
      if (res.data.length === 0) {
        list.innerHTML = `<div style="text-align:center;padding:20px;color:var(--text-light)">暂无获得${grade}的学生</div>`;
      } else {
        list.innerHTML = res.data.map(s => {
          const code = s.student_code || "";
          const displayName = formatStudentDisplay(s.student_name, code, zone);
          return `
          <div class="detail-item" data-sid="${s.student_id}" data-sname="${escapeHtml(displayName)}" style="cursor:pointer;">
            <span class="detail-name${privacyClass(zone)}">${formatStudentCodeHtml(code, zone)}${escapeHtml(displayName)}</span>
            <span class="detail-group">${escapeHtml(s.group_name)}</span>
            <span class="grade-badge grade-${s.grade.toLowerCase()}" style="font-size:.7rem;width:28px;height:22px;">${s.grade_label}</span>
          </div>`;
        }).join("");
        list.querySelectorAll(".detail-item").forEach(item => {
          item.addEventListener("click", () => {
            openStudentReport(parseInt(item.dataset.sid), item.dataset.sname);
          });
        });
      }
    }
  }
  modal.style.display = "";
}

async function openStudentReport(sid, name) {
  _currentReportSid = sid;
  _currentReportName = name;
  const modal = document.getElementById("studentReportModal");
  document.getElementById("reportModalTitle").textContent = `📄 ${name} - 作业报表`;
  document.getElementById("reportTbody").innerHTML = `<tr><td colspan="2" style="text-align:center;padding:20px;color:var(--text-light)">⏳ 加载中...</td></tr>`;
  modal.style.display = "";

  const res = await API.get(`/api/student/${sid}/report`);
  if (res.code === 0) {
    const d = res.data;
    document.getElementById("reportTotal").textContent = `共 ${d.total} 条记录`;
    const stats = d.stats;
    document.getElementById("reportStats").innerHTML = `
      <span class="report-stat-item grade-a-bg">⭐ A × ${stats.A || 0}</span>
      <span class="report-stat-item grade-b-bg">🔵 B × ${stats.B || 0}</span>
      <span class="report-stat-item grade-c-bg">🟡 C × ${stats.C || 0}</span>
      <span class="report-stat-item grade-l-bg">🌿 请假 × ${stats.L || 0}</span>
      <span class="report-stat-item grade-x-bg">⬜ 未交 × ${stats.X || 0}</span>
    `;

    if (d.records.length === 0) {
      document.getElementById("reportTbody").innerHTML = `<tr><td colspan="2" style="text-align:center;padding:20px;color:var(--text-lighter)">暂无记录</td></tr>`;
    } else {
      document.getElementById("reportTbody").innerHTML = d.records.map(r => `
        <tr>
          <td>${r.date}</td>
          <td class="grade-cell-${r.grade.toLowerCase()}">${r.grade_label}</td>
        </tr>`).join("");
    }
  } else {
    document.getElementById("reportTbody").innerHTML = `<tr><td colspan="2" style="text-align:center;padding:20px;color:var(--pink)">加载失败</td></tr>`;
  }
}

function exportStudentReport() {
  if (!_currentReportSid) return;
  const start = document.getElementById("exportStartDate")?.value || "";
  const end = document.getElementById("exportEndDate")?.value || "";
  let url = `/api/export/student/${_currentReportSid}?class_id=${State.currentClassId}`;
  if (start && end) url += `&start=${start}&end=${end}`;
  window.open(url, "_blank");
}

// ============================================================
// 工具函数
// ============================================================
function escapeHtml(text) {
  if (!text) return ""; const d = document.createElement("div"); d.textContent = text; return d.innerHTML;
}

/**
 * 显示模式下拉菜单设置
 */
function setupDisplayModeDropdown() {
  const dropdown = document.getElementById("displayModeDropdown");
  const btn = document.getElementById("displayModeBtn");
  const menu = document.getElementById("displayModeMenu");
  if (!dropdown || !btn || !menu) return;

  // 点击按钮切换菜单显示
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = menu.style.display !== "none";
    menu.style.display = isOpen ? "none" : "";
    dropdown.classList.toggle("open", !isOpen);
  });

  // 选择菜单项
  menu.querySelectorAll(".display-mode-option").forEach(opt => {
    opt.addEventListener("click", (e) => {
      e.stopPropagation();
      const mode = opt.dataset.mode;
      State.displayMode = mode;
      try {
        localStorage.setItem("classtrack_zone_display", mode === "auto" ? "auto" : "");
        localStorage.setItem("classtrack_privacy", mode === "code" ? "1" : "0");
      } catch (e) {}
      updateDisplayModeUI();
      refreshCurrentView();
      menu.style.display = "none";
      dropdown.classList.remove("open");
    });
  });

  // 点击外部关闭菜单
  document.addEventListener("click", () => {
    menu.style.display = "none";
    dropdown.classList.remove("open");
  });
}

/**
 * 更新显示模式按钮的外观
 */
function updateDisplayModeUI() {
  const icon = document.getElementById("displayModeIcon");
  const label = document.getElementById("displayModeLabel");
  if (!icon || !label) return;

  const config = {
    name:  { icon: "👤", label: "显示姓名" },
    code:  { icon: "🔒", label: "仅显示学号" },
    auto:  { icon: "🎯", label: "分区显示" },
  };
  const c = config[State.displayMode] || config.name;
  icon.textContent = c.icon;
  label.textContent = c.label;

  // 更新菜单选中状态
  document.querySelectorAll(".display-mode-option").forEach(opt => {
    opt.classList.toggle("active", opt.dataset.mode === State.displayMode);
  });

  // 同步提醒弹窗中的隐私开关
  const reminderToggle = document.getElementById("privacyToggle");
  if (reminderToggle) {
    reminderToggle.checked = reminderShowsCodes();
  }
}

/**
 * 等级显示文案（A/B/C 原样，X=未交，L=请假）
 * @param {string|null} g - 等级值
 */
function gradeDisplayLabel(g) {
  if (g === "X") return "未交";
  if (g === "L") return "请假";
  return g || "?";
}

/**
 * 根据 grade 判断显示分区
 * @param {string|null} grade - 作业等级 A/B/C/L(请假)/X 或 null
 * @returns {'completed'|'incomplete'|null} null 表示无分区上下文
 */
function getDisplayZone(grade) {
  if (State.displayMode !== "auto") return null;
  if (!grade) return null;
  if (grade === "X") return "incomplete";
  if (grade === "A" || grade === "B" || grade === "C" || grade === "L") return "completed";
  return null;
}

/**
 * 隐私模式辅助函数
 * @param {string} name - 学生姓名
 * @param {string} code - 学号
 * @param {string|null} zone - 显示分区: 'completed'|'incomplete'|null
 */
function formatStudentDisplay(name, code, zone) {
  if (zone === "incomplete") return code || name;
  if (zone === "completed") return name;
  if (State.displayMode === "code") return code || "???";
  return name;
}

/**
 * 生成学号前缀HTML
 */
function formatStudentCodeHtml(code, zone) {
  if (zone === "incomplete") return "";
  if (State.displayMode === "code" || !code) return "";
  return `<span class="student-code-label" style="font-family:monospace;color:var(--text-lighter);font-size:.75rem;margin-right:4px">${escapeHtml(code)}</span>`;
}

/**
 * 生成隐私模式的CSS class
 */
function privacyClass(zone) {
  if (zone === "incomplete") return " privacy-mode privacy-zone-incomplete";
  if (State.displayMode === "code") return " privacy-mode";
  return "";
}

function hashCode(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return hash;
}

/**
 * v2: 子元素逐项交错入场动画
 * @param {string|Element} container - 容器选择器或 DOM 元素
 * @param {string} childSelector - 子元素选择器
 * @param {number} baseDelay - 每项间隔（ms），默认 40
 */
function staggerEntrance(container, childSelector, baseDelay = 40) {
  const el = typeof container === "string" ? document.querySelector(container) : container;
  if (!el) return;
  const children = el.querySelectorAll(childSelector);
  children.forEach((child, i) => {
    child.style.animation = "none";
    child.offsetHeight; // force reflow
    child.style.animation = `staggerIn 0.35s var(--glass-spring) forwards`;
    child.style.animationDelay = `${i * baseDelay}ms`;
  });
}

/** v2: 元素闪烁高亮（拖放反馈） */
function flashElement(el) {
  if (!el) return;
  el.style.transition = 'none';
  el.style.backgroundColor = 'rgba(126,181,214,0.18)';
  requestAnimationFrame(() => {
    el.style.transition = 'background-color 0.5s var(--glass-spring)';
    el.style.backgroundColor = '';
  });
}

/** v2: 加载闪烁骨架 */
function showLoadingShimmer(selector) {
  const el = typeof selector === "string" ? document.querySelector(selector) : selector;
  if (!el) return () => {};
  el.style.opacity = '0.55';
  el.style.transition = 'opacity 0.2s ease';
  el.classList.add('loading-shimmer');
  return () => {
    el.style.opacity = '1';
    el.classList.remove('loading-shimmer');
  };
}

// ============================================================
// 成绩管理 (Exam Scores Management)
// ============================================================
function setupExamManagement() {
  // 仅在主页面有 examDate 元素时初始化
  if (!document.getElementById("examDate")) return;
  const dateEl = document.getElementById("examDate");
  if (dateEl) {
    const today = new Date().toISOString().slice(0, 10);
    dateEl.value = today;
    State.currentExamDate = today;
  }
  // 日期导航
  document.getElementById("btnExamPrevDay")?.addEventListener("click", () => navigateExamDate(-1));
  document.getElementById("btnExamNextDay")?.addEventListener("click", () => navigateExamDate(1));
  document.getElementById("btnExamToday")?.addEventListener("click", () => {
    const today = new Date().toISOString().slice(0, 10);
    document.getElementById("examDate").value = today;
    State.currentExamDate = today;
    renderExamView();
  });
  document.getElementById("examDate")?.addEventListener("change", () => {
    State.currentExamDate = document.getElementById("examDate").value;
    renderExamView();
  });
  // 新建/切换考试
  document.getElementById("btnNewExam")?.addEventListener("click", async () => {
    const name = document.getElementById("examNameInput").value.trim();
    if (!name) { showToast("请输入考试名称", "error"); return; }
    State.currentExamName = name;
    State.currentExamDate = document.getElementById("examDate").value;
    await loadExamList();
    renderExamView();
  });
  // 批量分数按钮
  document.querySelectorAll(".grade-batch-btn[data-score]").forEach(btn => {
    btn.addEventListener("click", () => {
      const score = parseFloat(btn.dataset.score);
      batchExamScores(score);
    });
  });
  // 自定义批量
  document.getElementById("btnExamCustomBatch")?.addEventListener("click", () => {
    const score = prompt("请输入要批量设置的分数：", "80");
    if (score !== null && !isNaN(parseFloat(score))) {
      batchExamScores(parseFloat(score));
    }
  });
  // 导入Excel
  document.getElementById("btnImportExamExcel")?.addEventListener("click", () => {
    document.getElementById("examFileInput").click();
  });
  document.getElementById("examFileInput")?.addEventListener("change", handleExamFileImport);
  // 导出
  document.getElementById("btnExportExamScores")?.addEventListener("click", exportExamScores);
}

function navigateExamDate(delta) {
  const el = document.getElementById("examDate");
  if (!el) return;
  const d = new Date(el.value + "T00:00:00");
  d.setDate(d.getDate() + delta);
  const ds = d.toISOString().slice(0, 10);
  el.value = ds;
  State.currentExamDate = ds;
  renderExamView();
}

async function loadExamList() {
  const res = await API.get(`/api/exam-scores/exams?class_id=${State.currentClassId}`);
  if (res.code === 0) {
    State.examList = res.data;
    renderExamList();
  }
}

function renderExamList() {
  const card = document.getElementById("examListCard");
  const list = document.getElementById("examList");
  if (!card || !list) return;
  if (State.examList.length === 0) {
    card.style.display = "none";
    return;
  }
  card.style.display = "";
  list.innerHTML = State.examList.map(e => {
    const isActive = e.exam_name === State.currentExamName && e.date === State.currentExamDate;
    return `<button class="exam-list-btn${isActive ? ' active' : ''}" data-name="${escapeHtml(e.exam_name)}" data-date="${e.date}" data-total="${e.total_score}">
      ${escapeHtml(e.exam_name)} <small>${e.date}</small>
    </button>`;
  }).join("");
  list.querySelectorAll(".exam-list-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      State.currentExamName = btn.dataset.name;
      State.currentExamDate = btn.dataset.date;
      document.getElementById("examNameInput").value = btn.dataset.name;
      document.getElementById("examDate").value = btn.dataset.date;
      document.getElementById("examTotalScore").value = btn.dataset.total || 100;
      renderExamView();
    });
  });
}

async function renderExamView() {
  const date = State.currentExamDate || document.getElementById("examDate")?.value || "";
  const name = State.currentExamName || document.getElementById("examNameInput")?.value.trim() || "";
  State.currentExamDate = date;
  State.currentExamName = name;

  // 加载考试列表
  await loadExamList();

  const container = document.getElementById("examGroups");
  if (!container) return;

  if (!name) {
    container.innerHTML = `<div class="empty-state"><span class="empty-icon">📊</span><p>请输入考试名称和日期后开始录入成绩<br>或点击「导入考试Excel」批量导入</p></div>`;
    document.getElementById("examStatsCards").style.display = "none";
    document.getElementById("examCountInfo").textContent = "";
    return;
  }

  if (State.groups.length === 0 || State.students.length === 0) {
    container.innerHTML = `<div class="empty-state"><span class="empty-icon">📊</span><p>请先在「班级分组」中导入学生并完成分组</p></div>`;
    return;
  }

  // 加载已有成绩
  await loadExamScores(name, date);
  const records = State.examCache[`${name}_${date}`] || {};

  // 统计
  const scores = Object.values(records).map(r => r.score).filter(s => s > 0);
  const total = Object.keys(records).length;
  const avg = scores.length > 0 ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1) : "0";
  const max = scores.length > 0 ? Math.max(...scores) : 0;
  const min = scores.length > 0 ? Math.min(...scores) : 0;
  document.getElementById("esTotal").textContent = total || State.students.length;
  document.getElementById("esAvg").textContent = avg;
  document.getElementById("esMax").textContent = max;
  document.getElementById("esMin").textContent = min;
  document.getElementById("examStatsCards").style.display = "";
  document.getElementById("examCountInfo").textContent = `已录入 ${total} 人`;

  // 渲染分组视图
  const groupStudents = {};
  for (const g of State.groups) groupStudents[g.id] = [];
  for (const s of State.students) {
    if (s.group_id && groupStudents[s.group_id]) groupStudents[s.group_id].push(s);
  }

  const totalScore = parseFloat(document.getElementById("examTotalScore")?.value || 100);
  let html = "";
  for (const g of State.groups) {
    const students = groupStudents[g.id] || [];
    html += `<div class="exam-group-column"><div class="hw-group-header" style="border-left:4px solid ${g.color}"><span class="group-name-dot" style="background:${g.color}"></span>${escapeHtml(g.name)}<span style="margin-left:auto;font-size:.72rem;color:var(--text-lighter)">${students.length}人</span></div><div class="hw-group-students">`;
    for (const s of students) {
      const record = records[s.id];
      const score = record ? record.score : "";
      const grade = record ? record.grade : "";
      html += `<div class="exam-student-row" data-student-id="${s.id}">
        <span class="hw-student-name">${escapeHtml(s.name)}</span>
        <div style="display:flex;align-items:center;gap:6px">
          <input type="number" class="exam-score-input" data-sid="${s.id}" value="${score}" placeholder="分数" min="0" max="${totalScore}" step="0.5" style="width:70px;padding:5px 6px;border:1px solid var(--border);border-radius:6px;text-align:center;font-size:.85rem">
          <span class="exam-grade-badge${grade ? ' grade-' + grade.toLowerCase() : ''}" style="font-size:.75rem;min-width:24px;text-align:center">${grade}</span>
        </div>
      </div>`;
    }
    html += `</div></div>`;
  }
  container.innerHTML = html;

  // 绑定输入事件
  container.querySelectorAll(".exam-score-input").forEach(inp => {
    inp.addEventListener("change", function() {
      const sid = parseInt(this.dataset.sid);
      const score = parseFloat(this.value) || 0;
      saveExamScore(sid, score, totalScore);
    });
  });
}

async function loadExamScores(examName, date) {
  const res = await API.get(`/api/exam-scores?exam_name=${encodeURIComponent(examName)}&date=${date}&class_id=${State.currentClassId}`);
  const key = `${examName}_${date}`;
  if (res.code === 0) {
    State.examCache[key] = res.data;
  } else {
    State.examCache[key] = {};
  }
}

async function saveExamScore(sid, score, totalScore) {
  const name = State.currentExamName;
  const date = State.currentExamDate;
  const res = await API.post("/api/exam-scores", {
    student_id: sid, exam_name: name, date, score, total_score: totalScore,
    class_id: State.currentClassId
  });
  if (res.code === 0) {
    // 更新缓存
    const key = `${name}_${date}`;
    if (!State.examCache[key]) State.examCache[key] = {};
    State.examCache[key][sid] = { student_id: sid, score, grade: res.data?.grade || "" };
    // 更新grade badge
    const badge = document.querySelector(`.exam-student-row[data-student-id="${sid}"] .exam-grade-badge`);
    if (badge) {
      const pct = totalScore > 0 ? score / totalScore * 100 : 0;
      let grade = "";
      if (pct >= 90) grade = "A";
      else if (pct >= 75) grade = "B";
      else if (pct >= 60) grade = "C";
      else grade = "D";
      badge.textContent = grade;
      badge.className = "exam-grade-badge grade-" + grade.toLowerCase();
    }
    // 更新统计
    updateExamStats();
  } else {
    showToast("保存失败: " + res.msg, "error");
  }
}

function updateExamStats() {
  const key = `${State.currentExamName}_${State.currentExamDate}`;
  const records = State.examCache[key] || {};
  const scores = Object.values(records).map(r => r.score).filter(s => s > 0);
  const total = Object.keys(records).length;
  document.getElementById("esTotal").textContent = total || State.students.length;
  document.getElementById("esAvg").textContent = scores.length > 0 ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1) : "0";
  document.getElementById("esMax").textContent = scores.length > 0 ? Math.max(...scores) : "0";
  document.getElementById("esMin").textContent = scores.length > 0 ? Math.min(...scores) : "0";
  document.getElementById("examCountInfo").textContent = `已录入 ${total} 人`;
}

async function batchExamScores(score) {
  const name = State.currentExamName;
  const date = State.currentExamDate;
  if (!name) { showToast("请先输入考试名称", "error"); return; }
  const totalScore = parseFloat(document.getElementById("examTotalScore")?.value || 100);

  if (!confirm(`确定将所有学生成绩设置为 ${score} 分吗？`)) return;

  const res = await API.post("/api/exam-scores/batch", {
    exam_name: name, date, score, total_score: totalScore,
    class_id: State.currentClassId
  });
  if (res.code === 0) {
    showToast(res.msg, "success");
    State.examCache[`${name}_${date}`] = {};
    await renderExamView();
  } else {
    showToast(res.msg, "error");
  }
}

async function handleExamFileImport() {
  const fi = document.getElementById("examFileInput");
  if (!fi.files.length) return;
  const fd = new FormData();
  fd.append("file", fi.files[0]);
  const date = document.getElementById("examDate").value;
  try {
    const r = await fetch(`/api/exam-scores/import?date=${date}&class_id=${State.currentClassId}`, { method: "POST", body: fd });
    const res = await r.json();
    if (res.code === 0) {
      showToast(res.msg, "success");
      // 自动填入考试信息
      const imported = res.data;
      await loadExamList();
      if (State.examList.length > 0) {
        const last = State.examList[0];
        State.currentExamName = last.exam_name;
        State.currentExamDate = last.date;
        document.getElementById("examNameInput").value = last.exam_name;
        document.getElementById("examDate").value = last.date;
        document.getElementById("examTotalScore").value = last.total_score || 100;
      }
      await renderExamView();
    } else {
      showToast(res.msg, "error");
    }
  } catch (e) {
    showToast("导入失败: " + e.message, "error");
  }
  fi.value = "";
}

function exportExamScores() {
  const name = State.currentExamName;
  const date = State.currentExamDate;
  if (!name) { showToast("请先选择考试", "error"); return; }
  window.open(`/api/export/exam-scores?exam_name=${encodeURIComponent(name)}&date=${date}&class_id=${State.currentClassId}`, "_blank");
}

// ============================================================
// 键盘快捷键
// ============================================================
document.addEventListener("keydown", e => {
  if (e.ctrlKey && e.key === "1") { e.preventDefault(); switchTab("grouping"); }
  if (e.ctrlKey && e.key === "2") { e.preventDefault(); switchTab("homework"); }
  if (e.ctrlKey && e.key === "3") { e.preventDefault(); switchTab("exams"); }
  if (e.ctrlKey && e.key === "4") { e.preventDefault(); switchTab("analytics"); }
  if (e.ctrlKey && e.key === "5") { e.preventDefault(); switchTab("export"); }
  if (e.ctrlKey && e.key === "a" && State.activeTab === "grouping") { e.preventDefault(); selectAll(); }
  if (e.key === "Escape" && State.activeTab === "grouping") { deselectAll(); }
});
