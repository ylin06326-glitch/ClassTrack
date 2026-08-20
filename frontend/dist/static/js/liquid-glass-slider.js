/**
 * 液态玻璃滑块效果 — 适配老版 ClassTrack 结构
 * 仅作用于：顶部 Tab 栏滑块 + 作业登记等级选择滑块
 */

(function() {
  'use strict';

  // ========== 顶部 Tab 栏液态玻璃滑块 ==========
  let lastTabIndex = 0;
  let tabIndicator = null;

  function initTabSlider() {
    const nav = document.getElementById('tabNav');
    if (!nav) return;

    tabIndicator = nav.querySelector('.tab-indicator');
    if (!tabIndicator) {
      tabIndicator = document.createElement('div');
      tabIndicator.className = 'tab-indicator';
      nav.insertBefore(tabIndicator, nav.firstChild);
    }

    const tabs = nav.querySelectorAll('.tab-btn');
    if (!tabs.length) return;

    // 初始化滑块位置
    requestAnimationFrame(() => {
      const activeTab = nav.querySelector('.tab-btn.active');
      if (activeTab) {
        moveTabIndicator(activeTab, false);
        lastTabIndex = Array.from(tabs).indexOf(activeTab);
      }
    });

    // 监听 Tab 点击
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', function() {
        // 点击变形
        if (tabIndicator) {
          tabIndicator.classList.add('pressed');
          setTimeout(() => tabIndicator.classList.remove('pressed'), 150);
        }

        // 移动变形
        const direction = index > lastTabIndex ? 'right' : 'left';
        moveTabIndicator(this, true, direction);
        lastTabIndex = index;
      });

      // mousedown 时添加 pressed 效果
      tab.addEventListener('mousedown', () => {
        if (tabIndicator) tabIndicator.classList.add('pressed');
      });

      tab.addEventListener('mouseup', () => {
        if (tabIndicator) setTimeout(() => tabIndicator.classList.remove('pressed'), 100);
      });

      tab.addEventListener('mouseleave', () => {
        if (tabIndicator) tabIndicator.classList.remove('pressed');
      });
    });

    // 窗口大小变化时重新定位
    window.addEventListener('resize', () => {
      const activeTab = nav.querySelector('.tab-btn.active');
      if (activeTab) moveTabIndicator(activeTab, false);
    });
  }

  function moveTabIndicator(tab, animate = true, direction = null) {
    if (!tabIndicator || !tab) return;

    const nav = document.getElementById('tabNav');
    if (!nav) return;

    const navRect = nav.getBoundingClientRect();
    const tabRect = tab.getBoundingClientRect();

    const left = tabRect.left - navRect.left;
    const width = tabRect.width;

    // 移除之前的移动方向类
    tabIndicator.classList.remove('moving-right', 'moving-left');

    if (animate && direction) {
      tabIndicator.classList.add(direction === 'right' ? 'moving-right' : 'moving-left');
      setTimeout(() => tabIndicator.classList.remove('moving-right', 'moving-left'), 400);
    }

    tabIndicator.style.left = left + 'px';
    tabIndicator.style.width = width + 'px';
  }


  // ========== 批量等级按钮液态玻璃滑块 ==========
  function initGradeBatchSliders() {
    // 找到所有批量等级按钮的父容器
    const batchBtns = document.querySelectorAll('.grade-batch-btn');
    if (!batchBtns.length) return;

    // 按父容器分组
    const containers = new Set();
    batchBtns.forEach(btn => containers.add(btn.parentElement));

    containers.forEach(container => {
      if (!container || container.classList.contains('grade-batch-container')) return;

      const btns = container.querySelectorAll('.grade-batch-btn');
      if (!btns.length) return;

      // 包裹在一个容器中
      const wrapper = document.createElement('div');
      wrapper.className = 'grade-batch-container';
      wrapper.style.display = 'inline-flex';
      wrapper.style.gap = '4px';

      // 创建滑块
      const indicator = document.createElement('div');
      indicator.className = 'grade-batch-indicator';
      wrapper.appendChild(indicator);

      // 把按钮移到 wrapper 中
      btns.forEach(btn => wrapper.appendChild(btn));
      container.appendChild(wrapper);

      // 初始化滑块位置
      requestAnimationFrame(() => {
        const activeBtn = wrapper.querySelector('.grade-batch-btn.active');
        if (activeBtn) {
          moveGradeIndicator(indicator, activeBtn, false);
          updateGradeIndicatorColor(indicator, activeBtn.dataset.grade);
        } else {
          indicator.style.width = '0px';
          indicator.style.opacity = '0';
        }
      });

      // 记录上一个按钮索引
      let lastIndex = 0;
      const btnArray = Array.from(btns);

      // 监听按钮点击
      btns.forEach((btn, index) => {
        btn.addEventListener('click', function() {
          indicator.classList.add('pressed');
          setTimeout(() => indicator.classList.remove('pressed'), 150);

          const direction = index > lastIndex ? 'right' : 'left';
          moveGradeIndicator(indicator, this, true, direction);
          updateGradeIndicatorColor(indicator, this.dataset.grade);
          lastIndex = index;

          // 更新 active 状态
          btns.forEach(b => b.classList.remove('active'));
          this.classList.add('active');
        });

        btn.addEventListener('mousedown', () => indicator.classList.add('pressed'));
        btn.addEventListener('mouseup', () => setTimeout(() => indicator.classList.remove('pressed'), 100));
        btn.addEventListener('mouseleave', () => indicator.classList.remove('pressed'));
      });

      window.addEventListener('resize', () => {
        const activeBtn = wrapper.querySelector('.grade-batch-btn.active');
        if (activeBtn) moveGradeIndicator(indicator, activeBtn, false);
      });

      wrapper._gradeIndicator = indicator;
    });
  }


  // ========== 学生行内等级按钮滑块 ==========
  function initGradeQuickSliders() {
    document.querySelectorAll('.grade-quick-select').forEach(container => {
      if (container.querySelector('.grade-quick-indicator')) return;

      const btns = container.querySelectorAll('.grade-qbtn');
      if (!btns.length) return;

      // 创建滑块
      const indicator = document.createElement('div');
      indicator.className = 'grade-quick-indicator';
      container.insertBefore(indicator, container.firstChild);

      // 初始化滑块位置
      requestAnimationFrame(() => {
        const activeBtn = container.querySelector('.grade-qbtn.active');
        if (activeBtn) {
          moveQuickIndicator(indicator, activeBtn, false);
          updateGradeIndicatorColor(indicator, activeBtn.dataset.grade);
        } else {
          indicator.style.width = '0px';
          indicator.style.opacity = '0';
        }
      });

      let lastIndex = 0;
      const btnArray = Array.from(btns);

      btns.forEach((btn, index) => {
        btn.addEventListener('click', function() {
          indicator.classList.add('pressed');
          setTimeout(() => indicator.classList.remove('pressed'), 150);

          const direction = index > lastIndex ? 'right' : 'left';
          moveQuickIndicator(indicator, this, true, direction);
          updateGradeIndicatorColor(indicator, this.dataset.grade);
          lastIndex = index;
        });
      });

      container._gradeIndicator = indicator;
    });
  }


  // ========== 通用函数 ==========
  function moveGradeIndicator(indicator, btn, animate = true, direction = null) {
    if (!indicator || !btn) return;

    const container = indicator.parentElement;
    if (!container) return;

    const containerRect = container.getBoundingClientRect();
    const btnRect = btn.getBoundingClientRect();

    const paddingLeft = parseFloat(getComputedStyle(container).paddingLeft) || 0;
    const left = btnRect.left - containerRect.left - paddingLeft;
    const width = btnRect.width;

    indicator.classList.remove('moving-right', 'moving-left');
    indicator.style.opacity = '1';

    if (animate && direction) {
      indicator.classList.add(direction === 'right' ? 'moving-right' : 'moving-left');
      setTimeout(() => indicator.classList.remove('moving-right', 'moving-left'), 400);
    }

    indicator.style.left = left + 'px';
    indicator.style.width = width + 'px';
  }

  function moveQuickIndicator(indicator, btn, animate = true, direction = null) {
    if (!indicator || !btn) return;

    const container = indicator.parentElement;
    if (!container) return;

    const containerRect = container.getBoundingClientRect();
    const btnRect = btn.getBoundingClientRect();

    const paddingLeft = parseFloat(getComputedStyle(container).paddingLeft) || 0;
    const left = btnRect.left - containerRect.left - paddingLeft;
    const width = btnRect.width;

    indicator.classList.remove('moving-right', 'moving-left');
    indicator.style.opacity = '1';

    if (animate && direction) {
      indicator.classList.add(direction === 'right' ? 'moving-right' : 'moving-left');
      setTimeout(() => indicator.classList.remove('moving-right', 'moving-left'), 350);
    }

    indicator.style.left = left + 'px';
    indicator.style.width = width + 'px';
  }

  function updateGradeIndicatorColor(indicator, grade) {
    if (!indicator) return;

    indicator.classList.remove('grade-A', 'grade-B', 'grade-C', 'grade-other');

    if (grade === 'A') {
      indicator.classList.add('grade-A');
    } else if (grade === 'B') {
      indicator.classList.add('grade-B');
    } else if (grade === 'C') {
      indicator.classList.add('grade-C');
    } else {
      indicator.classList.add('grade-other');
    }
  }


  // ========== 外部 API ==========
  window.updateGradeSlider = function(container, activeBtn) {
    if (!container || !activeBtn) return;
    const indicator = container._gradeIndicator;
    if (indicator) {
      moveGradeIndicator(indicator, activeBtn, true);
      updateGradeIndicatorColor(indicator, activeBtn.dataset.grade);
    }
  };


  // ========== 初始化 ==========
  function init() {
    initTabSlider();
    initGradeBatchSliders();
    initGradeQuickSliders();
    console.log('✅ 液态玻璃滑块效果已初始化（Tab栏 + 作业登记等级选择）');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // 页面切换后重新初始化（SPA）
  let lastUrl = location.href;
  new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      setTimeout(init, 100);
    }
  }).observe(document, { subtree: true, childList: true });

})();
