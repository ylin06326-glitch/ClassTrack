/**
 * 液态玻璃滑块效果
 * 参考 liquid-glass-studio
 * 功能：移动变形、点击变形、颜色变化
 */

(function() {
  'use strict';

  // ========== Tab 栏液态玻璃滑块 ==========
  let lastTabIndex = 0;
  let tabIndicator = null;

  function initTabSlider() {
    const nav = document.getElementById('tabNav');
    if (!nav) return;

    tabIndicator = nav.querySelector('.tab-indicator');
    if (!tabIndicator) {
      // 如果没有滑块，创建一个
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
      tab.addEventListener('click', function(e) {
        // 点击变形
        if (tabIndicator) {
          tabIndicator.classList.add('pressed');
          setTimeout(() => {
            tabIndicator.classList.remove('pressed');
          }, 150);
        }

        // 移动变形
        const direction = index > lastTabIndex ? 'right' : 'left';
        moveTabIndicator(this, true, direction);
        lastTabIndex = index;
      });

      // mousedown 时添加 pressed 效果
      tab.addEventListener('mousedown', function() {
        if (tabIndicator) {
          tabIndicator.classList.add('pressed');
        }
      });

      tab.addEventListener('mouseup', function() {
        if (tabIndicator) {
          setTimeout(() => {
            tabIndicator.classList.remove('pressed');
          }, 100);
        }
      });

      tab.addEventListener('mouseleave', function() {
        if (tabIndicator) {
          tabIndicator.classList.remove('pressed');
        }
      });
    });

    // 窗口大小变化时重新定位
    window.addEventListener('resize', () => {
      const activeTab = nav.querySelector('.tab-btn.active');
      if (activeTab) {
        moveTabIndicator(activeTab, false);
      }
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
      // 添加移动方向变形
      tabIndicator.classList.add(direction === 'right' ? 'moving-right' : 'moving-left');

      // 动画结束后移除变形类
      setTimeout(() => {
        tabIndicator.classList.remove('moving-right', 'moving-left');
      }, 400);
    }

    tabIndicator.style.left = left + 'px';
    tabIndicator.style.width = width + 'px';
  }


  // ========== 等级按钮组液态玻璃滑块 ==========
  function initGradeSliders() {
    // 为每个等级按钮组创建滑块
    document.querySelectorAll('.grade-quick-select, .grade-batch-container').forEach(container => {
      if (container.querySelector('.grade-slider-indicator, .grade-batch-indicator')) return;

      const buttons = container.querySelectorAll('.grade-qbtn, .grade-batch-btn');
      if (!buttons.length) return;

      // 创建滑块
      const indicator = document.createElement('div');
      const isBatch = container.classList.contains('grade-batch-container');
      indicator.className = isBatch ? 'grade-batch-indicator' : 'grade-slider-indicator';
      container.style.position = 'relative';
      container.insertBefore(indicator, container.firstChild);

      // 初始化滑块位置
      requestAnimationFrame(() => {
        const activeBtn = container.querySelector('.active');
        if (activeBtn) {
          moveGradeIndicator(indicator, activeBtn, false);
        } else {
          // 默认隐藏滑块
          indicator.style.width = '0px';
          indicator.style.opacity = '0';
        }
      });

      // 记录上一个按钮索引
      let lastIndex = 0;
      const btnArray = Array.from(buttons);

      // 监听按钮点击
      buttons.forEach((btn, index) => {
        btn.addEventListener('click', function(e) {
          // 点击变形
          indicator.classList.add('pressed');
          setTimeout(() => indicator.classList.remove('pressed'), 150);

          // 移动变形
          const direction = index > lastIndex ? 'right' : 'left';
          moveGradeIndicator(indicator, this, true, direction);
          lastIndex = index;

          // 更新颜色
          updateGradeIndicatorColor(indicator, this.dataset.grade);
        });

        btn.addEventListener('mousedown', () => indicator.classList.add('pressed'));
        btn.addEventListener('mouseup', () => setTimeout(() => indicator.classList.remove('pressed'), 100));
        btn.addEventListener('mouseleave', () => indicator.classList.remove('pressed'));
      });

      // 窗口大小变化时重新定位
      window.addEventListener('resize', () => {
        const activeBtn = container.querySelector('.active');
        if (activeBtn) {
          moveGradeIndicator(indicator, activeBtn, false);
        }
      });

      // 存储引用，方便外部更新
      container._gradeIndicator = indicator;
    });
  }

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

  function updateGradeIndicatorColor(indicator, grade) {
    if (!indicator) return;

    // 移除所有颜色类
    indicator.classList.remove('grade-A', 'grade-B', 'grade-C', 'grade-other');

    // 添加对应颜色类
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


  // ========== 外部 API：更新等级滑块（供 app.js 调用） ==========
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
    initGradeSliders();
    console.log('✅ 液态玻璃滑块效果已初始化');
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
