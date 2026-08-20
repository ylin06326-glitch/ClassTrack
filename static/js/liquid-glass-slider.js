/**
 * 液态玻璃滑块效果 — 修复动态元素初始化
 * 仅作用于：顶部 Tab 栏滑块 + 作业登记等级选择滑块
 */

(function() {
  'use strict';

  // 已初始化的容器集合（避免重复初始化）
  const initializedContainers = new WeakSet();
  const initializedQuickSelects = new WeakSet();

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

    function setIndicatorPosition(left, width) {
      indicator.style.left = left + 'px';
      indicator.style.width = width + 'px';
    }

    function springTo(targetLeft, targetWidth, initialVelocity = 0) {
      const startLeft = parseFloat(indicator.style.left) || 0;
      const startWidth = parseFloat(indicator.style.width) || 0;
      const startTime = performance.now();
      const duration = 500;

      indicator.classList.remove('dragging', 'drag-fast-right', 'drag-fast-left');
      indicator.classList.add(initialVelocity >= 0 ? 'moving-right' : 'moving-left');

      function animate(now) {
        const elapsed = now - startTime;
        const t = Math.min(elapsed / duration, 1);
        const springT = 1 - Math.pow(1 - t, 3) * (1 + 3 * t + 3 * t * t);

        const left = startLeft + (targetLeft - startLeft) * springT;
        const width = startWidth + (targetWidth - startWidth) * springT;

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

    function projectPosition(initialVelocity) {
      const decelerationRate = 0.998;
      return (initialVelocity / 1000) * decelerationRate / (1 - decelerationRate);
    }

    function rubberband(overshoot, dimension, constant = 0.55) {
      return (overshoot * dimension * constant) / (dimension + constant * Math.abs(overshoot));
    }

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

      currentIndex = getActiveIndex ? getActiveIndex() : currentIndex;
    });

    indicator.addEventListener('pointermove', function(e) {
      if (!isDragging) return;

      const now = performance.now();
      const dt = now - lastTime;

      if (dt > 0) {
        velocity = (e.clientX - lastX) / dt * 1000;
      }

      lastX = e.clientX;
      lastTime = now;

      const deltaX = e.clientX - startX;
      let newLeft = startLeft + deltaX;

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

      const projectedDelta = projectPosition(velocity);
      const currentCenter = parseFloat(indicator.style.left) + parseFloat(indicator.style.width) / 2 + projectedDelta;

      const targetIndex = findNearestIndex(currentCenter + indicator.parentElement.getBoundingClientRect().left);

      if (targetIndex !== currentIndex || Math.abs(velocity) > 50) {
        const targetPos = getIndicatorPosition(targetIndex);
        springTo(targetPos.left, targetPos.width, velocity);

        if (onSelect) {
          setTimeout(() => onSelect(targetIndex), 50);
        }
        currentIndex = targetIndex;
      } else {
        const currentPos = getIndicatorPosition(currentIndex);
        springTo(currentPos.left, currentPos.width, 0);
      }
    }

    indicator.addEventListener('pointerup', endDrag);
    indicator.addEventListener('pointercancel', endDrag);

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
      },
      refresh: function() {
        const pos = getIndicatorPosition(currentIndex);
        setIndicatorPosition(pos.left, pos.width);
      }
    };
  }


  // ============================================================
  // 顶部 Tab 栏液态玻璃滑块
  // ============================================================
  let tabDraggable = null;

  function initTabSlider() {
    const nav = document.getElementById('tabNav');
    if (!nav || initializedContainers.has(nav)) return;

    initializedContainers.add(nav);

    let indicator = nav.querySelector('.tab-indicator');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.className = 'tab-indicator';
      nav.insertBefore(indicator, nav.firstChild);
    }

    const tabs = nav.querySelectorAll('.tab-btn');
    if (!tabs.length) return;

    function getActiveIndex() {
      return Array.from(tabs).findIndex(tab => tab.classList.contains('active'));
    }

    requestAnimationFrame(() => {
      const activeIndex = getActiveIndex();
      if (activeIndex >= 0) {
        const navRect = nav.getBoundingClientRect();
        const tabRect = tabs[activeIndex].getBoundingClientRect();
        indicator.style.left = (tabRect.left - navRect.left) + 'px';
        indicator.style.width = tabRect.width + 'px';
      }
    });

    tabDraggable = makeDraggable(indicator, tabs, function(index) {
      tabs.forEach(t => t.classList.remove('active'));
      tabs[index].classList.add('active');
      tabs[index].click();
    }, getActiveIndex);

    tabs.forEach((tab, index) => {
      tab.addEventListener('click', function() {
        if (tabDraggable) {
          tabDraggable.setIndex(index);
        }
      });
    });

    console.log('✅ Tab 栏液态玻璃滑块已初始化');
  }


  // ============================================================
  // 批量等级按钮液态玻璃滑块
  // ============================================================
  function initGradeBatchSliders() {
    const batchBtns = document.querySelectorAll('.grade-batch-btn:not([data-slider-initialized])');
    if (!batchBtns.length) return;

    const containers = new Set();
    batchBtns.forEach(btn => containers.add(btn.parentElement));

    containers.forEach(container => {
      if (!container || initializedContainers.has(container)) return;

      const btns = container.querySelectorAll('.grade-batch-btn');
      if (!btns.length) return;

      initializedContainers.add(container);
      btns.forEach(btn => btn.setAttribute('data-slider-initialized', 'true'));

      // 创建 wrapper 容器
      const wrapper = document.createElement('div');
      wrapper.className = 'grade-batch-container';
      wrapper.style.display = 'inline-flex';
      wrapper.style.gap = '4px';

      // 创建滑块
      const indicator = document.createElement('div');
      indicator.className = 'grade-batch-indicator';
      wrapper.appendChild(indicator);

      // 只把 .grade-batch-btn 移到 wrapper 中（不包含 span 等其他元素）
      btns.forEach(btn => wrapper.appendChild(btn));
      container.appendChild(wrapper);

      function getActiveIndex() {
        return Array.from(btns).findIndex(btn => btn.classList.contains('active'));
      }

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

      const draggable = makeDraggable(indicator, btns, function(index) {
        btns.forEach(b => b.classList.remove('active'));
        btns[index].classList.add('active');
        updateGradeIndicatorColor(indicator, btns[index].dataset.grade);
        btns[index].click();
      }, getActiveIndex);

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

      console.log('✅ 批量等级液态玻璃滑块已初始化');
    });
  }


  // ============================================================
  // 学生行内等级按钮滑块（动态生成）
  // ============================================================
  function initGradeQuickSliders() {
    // 找到所有包含 .grade-qbtn 的容器
    const qbtns = document.querySelectorAll('.grade-qbtn:not([data-slider-initialized])');
    if (!qbtns.length) return;

    // 按父容器分组
    const containers = new Set();
    qbtns.forEach(btn => {
      let parent = btn.parentElement;
      // 向上找，直到找到一个合适的容器（不是 .hw-student-row 本身）
      while (parent && !parent.classList.contains('grade-quick-select') && parent.tagName !== 'BODY') {
        if (parent.children.length <= 8 && parent.querySelectorAll('.grade-qbtn').length >= 3) {
          break;
        }
        parent = parent.parentElement;
      }
      if (parent) containers.add(parent);
    });

    containers.forEach(container => {
      if (!container || initializedQuickSelects.has(container)) return;

      const btns = container.querySelectorAll('.grade-qbtn');
      if (!btns.length || btns.length < 2) return;

      initializedQuickSelects.add(container);
      btns.forEach(btn => btn.setAttribute('data-slider-initialized', 'true'));

      // 添加容器类名
      container.classList.add('grade-quick-select');

      // 创建滑块
      const indicator = document.createElement('div');
      indicator.className = 'grade-quick-indicator';
      container.insertBefore(indicator, container.firstChild);

      function getActiveIndex() {
        return Array.from(btns).findIndex(btn => btn.classList.contains('active'));
      }

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

      const draggable = makeDraggable(indicator, btns, function(index) {
        btns.forEach(b => b.classList.remove('active'));
        btns[index].classList.add('active');
        updateGradeIndicatorColor(indicator, btns[index].dataset.grade);
        btns[index].click();
      }, getActiveIndex);

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

      console.log('✅ 学生行内等级液态玻璃滑块已初始化，共 ' + btns.length + ' 个按钮');
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
  window.refreshLiquidGlassSliders = function() {
    initGradeBatchSliders();
    initGradeQuickSliders();
  };

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
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // 监听 DOM 变化，初始化动态生成的等级按钮
  let domChangeTimer = null;
  new MutationObserver(() => {
    if (domChangeTimer) clearTimeout(domChangeTimer);
    domChangeTimer = setTimeout(() => {
      initGradeBatchSliders();
      initGradeQuickSliders();
    }, 200);
  }).observe(document.body, { subtree: true, childList: true });

  console.log('✅ 液态玻璃滑块效果已加载（支持动态元素初始化）');

})();
