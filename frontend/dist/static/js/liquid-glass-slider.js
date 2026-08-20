/**
 * 液态玻璃滑块效果 — 可拖拽长椭圆胶囊形 + 光线折射
 * 仅作用于：顶部 Tab 栏滑块 + 作业登记等级选择滑块
 *
 * 功能：
 * - 点击标签页切换
 * - 按住滑块拖拽切换
 * - 拖拽过程中实时变形（根据速度 skewX + scaleX）
 * - 拖拽结束弹簧动画到最近目标
 * - 动量预测（根据释放速度预测目标）
 * - 光线折射效果（CSS 多层渐变 + 色散边缘）
 */

(function() {
  'use strict';

  // 弹簧动画参数
  const SPRING = {
    damping: 0.82,
    response: 0.35
  };

  // 动量预测参数
  const DECELERATION_RATE = 0.998;


  // ============================================================
  // 通用：使元素可拖拽
  // ============================================================
  function makeDraggable(indicator, items, onSelect, getActiveIndex) {
    if (!indicator || !items || !items.length) return;

    let isDragging = false;
    let startX = 0;
    let startLeft = 0;
    let lastX = 0;
    let lastTime = 0;
    let velocity = 0;
    let currentIndex = getActiveIndex ? getActiveIndex() : 0;

    // 计算滑块位置
    function getIndicatorPosition(index) {
      const container = indicator.parentElement;
      if (!container || !items[index]) return { left: 0, width: 0 };

      const containerRect = container.getBoundingClientRect();
      const itemRect = items[index].getBoundingClientRect();
      const paddingLeft = parseFloat(getComputedStyle(container).paddingLeft) || 0;

      return {
        left: itemRect.left - containerRect.left - paddingLeft,
        width: itemRect.width
      };
    }

    // 设置滑块位置（无动画）
    function setIndicatorPosition(left, width) {
      indicator.style.left = left + 'px';
      indicator.style.width = width + 'px';
    }

    // 弹簧动画到目标
    function springTo(targetLeft, targetWidth, initialVelocity = 0) {
      const startLeft = parseFloat(indicator.style.left) || 0;
      const startWidth = parseFloat(indicator.style.width) || 0;
      const startTime = performance.now();
      const duration = 500; // 弹簧动画持续时间

      indicator.classList.remove('dragging', 'drag-fast-right', 'drag-fast-left');
      indicator.classList.add(initialVelocity > 0 ? 'moving-right' : 'moving-left');

      function animate(now) {
        const elapsed = now - startTime;
        const t = Math.min(elapsed / duration, 1);

        // 弹簧缓动（近似 Apple spring）
        const springT = 1 - Math.pow(1 - t, 3) * (1 + 3 * t + 3 * t * t);
        const eased = springT;

        const left = startLeft + (targetLeft - startLeft) * eased;
        const width = startWidth + (targetWidth - startWidth) * eased;

        setIndicatorPosition(left, width);

        if (t < 1) {
          requestAnimationFrame(animate);
        } else {
          setIndicatorPosition(targetLeft, targetWidth);
          indicator.classList.remove('moving-right', 'moving-left');
        }
      }

      requestAnimationFrame(animate);
    }

    // 找到最近的目标索引
    function findNearestIndex(centerX) {
      const container = indicator.parentElement;
      if (!container) return currentIndex;

      const containerRect = container.getBoundingClientRect();
      const paddingLeft = parseFloat(getComputedStyle(container).paddingLeft) || 0;
      const relativeCenter = centerX - containerRect.left - paddingLeft;

      let nearest = 0;
      let minDist = Infinity;

      items.forEach((item, index) => {
        const itemRect = item.getBoundingClientRect();
        const itemCenter = itemRect.left - containerRect.left - paddingLeft + itemRect.width / 2;
        const dist = Math.abs(relativeCenter - itemCenter);
        if (dist < minDist) {
          minDist = dist;
          nearest = index;
        }
      });

      return nearest;
    }

    // 动量预测
    function projectPosition(initialVelocity) {
      return (initialVelocity / 1000) * DECELERATION_RATE / (1 - DECELERATION_RATE);
    }

    // Pointer Events
    indicator.addEventListener('pointerdown', function(e) {
      e.preventDefault();
      e.stopPropagation();

      isDragging = true;
      startX = e.clientX;
      lastX = e.clientX;
      lastTime = performance.now();
      velocity = 0;
      startLeft = parseFloat(indicator.style.left) || 0;

      indicator.classList.add('dragging', 'pressed');
      indicator.setPointerCapture(e.pointerId);

      // 记录当前激活索引
      currentIndex = getActiveIndex ? getActiveIndex() : currentIndex;
    });

    indicator.addEventListener('pointermove', function(e) {
      if (!isDragging) return;

      const now = performance.now();
      const dt = now - lastTime;

      if (dt > 0) {
        velocity = (e.clientX - lastX) / dt * 1000; // px/s
      }

      lastX = e.clientX;
      lastTime = now;

      const deltaX = e.clientX - startX;
      let newLeft = startLeft + deltaX;

      // 橡皮筋边界
      const container = indicator.parentElement;
      if (container) {
        const firstPos = getIndicatorPosition(0);
        const lastPos = getIndicatorPosition(items.length - 1);
        const minLeft = firstPos.left;
        const maxLeft = lastPos.left;

        if (newLeft < minLeft) {
          const overshoot = minLeft - newLeft;
          newLeft = minLeft - rubberband(overshoot, container.offsetWidth);
        } else if (newLeft > maxLeft) {
          const overshoot = newLeft - maxLeft;
          newLeft = maxLeft + rubberband(overshoot, container.offsetWidth);
        }
      }

      // 根据速度添加变形
      indicator.classList.remove('drag-fast-right', 'drag-fast-left');
      if (Math.abs(velocity) > 300) {
        indicator.classList.add(velocity > 0 ? 'drag-fast-right' : 'drag-fast-left');
      }

      setIndicatorPosition(newLeft, parseFloat(indicator.style.width) || 0);
    });

    function endDrag(e) {
      if (!isDragging) return;
      isDragging = false;

      indicator.classList.remove('dragging', 'pressed', 'drag-fast-right', 'drag-fast-left');

      try {
        indicator.releasePointerCapture(e.pointerId);
      } catch (err) {}

      // 动量预测目标位置
      const projectedDelta = projectPosition(velocity);
      const currentCenter = parseFloat(indicator.style.left) + parseFloat(indicator.style.width) / 2 + projectedDelta;

      // 找到最近的目标
      const targetIndex = findNearestIndex(currentCenter + indicator.parentElement.getBoundingClientRect().left);

      if (targetIndex !== currentIndex || Math.abs(velocity) > 50) {
        const targetPos = getIndicatorPosition(targetIndex);
        springTo(targetPos.left, targetPos.width, velocity);

        // 触发选择
        if (onSelect) {
          setTimeout(() => onSelect(targetIndex), 50);
        }
        currentIndex = targetIndex;
      } else {
        // 回到原位
        const currentPos = getIndicatorPosition(currentIndex);
        springTo(currentPos.left, currentPos.width, 0);
      }
    }

    indicator.addEventListener('pointerup', endDrag);
    indicator.addEventListener('pointercancel', endDrag);

    // 窗口大小变化时重新定位
    window.addEventListener('resize', () => {
      if (!isDragging) {
        const pos = getIndicatorPosition(currentIndex);
        setIndicatorPosition(pos.left, pos.width);
      }
    });

    return {
      setIndex: function(index) {
        currentIndex = index;
        const pos = getIndicatorPosition(index);
        springTo(pos.left, pos.width, 0);
      },
      getIndex: function() {
        return currentIndex;
      }
    };
  }

  // 橡皮筋函数
  function rubberband(overshoot, dimension, constant = 0.55) {
    return (overshoot * dimension * constant) / (dimension + constant * Math.abs(overshoot));
  }


  // ============================================================
  // 顶部 Tab 栏液态玻璃滑块
  // ============================================================
  let tabDraggable = null;

  function initTabSlider() {
    const nav = document.getElementById('tabNav');
    if (!nav) return;

    let indicator = nav.querySelector('.tab-indicator');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.className = 'tab-indicator';
      nav.insertBefore(indicator, nav.firstChild);
    }

    const tabs = nav.querySelectorAll('.tab-btn');
    if (!tabs.length) return;

    // 获取当前激活索引
    function getActiveIndex() {
      return Array.from(tabs).findIndex(tab => tab.classList.contains('active'));
    }

    // 初始化滑块位置
    requestAnimationFrame(() => {
      const activeIndex = getActiveIndex();
      if (activeIndex >= 0) {
        const containerRect = nav.getBoundingClientRect();
        const tabRect = tabs[activeIndex].getBoundingClientRect();
        indicator.style.left = (tabRect.left - containerRect.left) + 'px';
        indicator.style.width = tabRect.width + 'px';
      }
    });

    // 使滑块可拖拽
    tabDraggable = makeDraggable(indicator, tabs, function(index) {
      // 拖拽结束后切换 Tab
      tabs.forEach(t => t.classList.remove('active'));
      tabs[index].classList.add('active');
      tabs[index].click();
    }, getActiveIndex);

    // 监听 Tab 点击（点击切换）
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', function() {
        if (tabDraggable) {
          tabDraggable.setIndex(index);
        }
      });
    });
  }


  // ============================================================
  // 批量等级按钮液态玻璃滑块
  // ============================================================
  function initGradeBatchSliders() {
    const batchBtns = document.querySelectorAll('.grade-batch-btn');
    if (!batchBtns.length) return;

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

      // 获取当前激活索引
      function getActiveIndex() {
        return Array.from(btns).findIndex(btn => btn.classList.contains('active'));
      }

      // 初始化滑块位置
      requestAnimationFrame(() => {
        const activeIndex = getActiveIndex();
        if (activeIndex >= 0) {
          const wrapperRect = wrapper.getBoundingClientRect();
          const btnRect = btns[activeIndex].getBoundingClientRect();
          const paddingLeft = parseFloat(getComputedStyle(wrapper).paddingLeft) || 0;
          indicator.style.left = (btnRect.left - wrapperRect.left - paddingLeft) + 'px';
          indicator.style.width = btnRect.width + 'px';
          updateGradeIndicatorColor(indicator, btns[activeIndex].dataset.grade);
        } else {
          indicator.style.width = '0px';
          indicator.style.opacity = '0';
        }
      });

      // 使滑块可拖拽
      const draggable = makeDraggable(indicator, btns, function(index) {
        btns.forEach(b => b.classList.remove('active'));
        btns[index].classList.add('active');
        updateGradeIndicatorColor(indicator, btns[index].dataset.grade);
        btns[index].click();
      }, getActiveIndex);

      // 监听按钮点击
      btns.forEach((btn, index) => {
        btn.addEventListener('click', function() {
          if (draggable) {
            draggable.setIndex(index);
          }
          updateGradeIndicatorColor(indicator, this.dataset.grade);
        });
      });

      wrapper._gradeIndicator = indicator;
      wrapper._gradeDraggable = draggable;
    });
  }


  // ============================================================
  // 学生行内等级按钮滑块
  // ============================================================
  function initGradeQuickSliders() {
    document.querySelectorAll('.grade-quick-select').forEach(container => {
      if (container.querySelector('.grade-quick-indicator')) return;

      const btns = container.querySelectorAll('.grade-qbtn');
      if (!btns.length) return;

      // 创建滑块
      const indicator = document.createElement('div');
      indicator.className = 'grade-quick-indicator';
      container.insertBefore(indicator, container.firstChild);

      // 获取当前激活索引
      function getActiveIndex() {
        return Array.from(btns).findIndex(btn => btn.classList.contains('active'));
      }

      // 初始化滑块位置
      requestAnimationFrame(() => {
        const activeIndex = getActiveIndex();
        if (activeIndex >= 0) {
          const containerRect = container.getBoundingClientRect();
          const btnRect = btns[activeIndex].getBoundingClientRect();
          const paddingLeft = parseFloat(getComputedStyle(container).paddingLeft) || 0;
          indicator.style.left = (btnRect.left - containerRect.left - paddingLeft) + 'px';
          indicator.style.width = btnRect.width + 'px';
          updateGradeIndicatorColor(indicator, btns[activeIndex].dataset.grade);
        } else {
          indicator.style.width = '0px';
          indicator.style.opacity = '0';
        }
      });

      // 使滑块可拖拽
      const draggable = makeDraggable(indicator, btns, function(index) {
        btns.forEach(b => b.classList.remove('active'));
        btns[index].classList.add('active');
        updateGradeIndicatorColor(indicator, btns[index].dataset.grade);
        btns[index].click();
      }, getActiveIndex);

      // 监听按钮点击
      btns.forEach((btn, index) => {
        btn.addEventListener('click', function() {
          if (draggable) {
            draggable.setIndex(index);
          }
          updateGradeIndicatorColor(indicator, this.dataset.grade);
        });
      });

      container._gradeIndicator = indicator;
      container._gradeDraggable = draggable;
    });
  }


  // ============================================================
  // 通用函数
  // ============================================================
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


  // ============================================================
  // 外部 API
  // ============================================================
  window.updateGradeSlider = function(container, activeBtn) {
    if (!container || !activeBtn) return;
    const indicator = container._gradeIndicator;
    const draggable = container._gradeDraggable;
    if (indicator && draggable) {
      const btns = container.querySelectorAll('.grade-qbtn, .grade-batch-btn');
      const index = Array.from(btns).indexOf(activeBtn);
      if (index >= 0) {
        draggable.setIndex(index);
        updateGradeIndicatorColor(indicator, activeBtn.dataset.grade);
      }
    }
  };


  // ============================================================
  // 初始化
  // ============================================================
  function init() {
    initTabSlider();
    initGradeBatchSliders();
    initGradeQuickSliders();
    console.log('✅ 液态玻璃滑块效果已初始化（可拖拽长椭圆 + 光线折射）');
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
