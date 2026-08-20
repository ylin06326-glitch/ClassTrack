/**
 * 液态玻璃滑块效果 — 修复版
 * 仅作用于：顶部 Tab 栏滑块 + 作业登记等级选择滑块
 */

(function() {
  'use strict';

  const initializedContainers = new WeakSet();

  // ============================================================
  // 通用：使元素可拖拽
  // ============================================================
  function makeDraggable(indicator, items, onSelect, getActiveIndex) {
    if (!indicator || !items || !items.length) return null;

    let isDragging = false;
    let startX = 0;
    let startLeft = 0;
    let lastX = 0;
    let lastTime = 0;
    let velocity = 0;
    let currentIndex = getActiveIndex ? getActiveIndex() : 0;

    function getPos(index) {
      const container = indicator.parentElement;
      if (!container || !items[index]) return { left: 0, width: 0 };
      const cRect = container.getBoundingClientRect();
      const iRect = items[index].getBoundingClientRect();
      const pl = parseFloat(getComputedStyle(container).paddingLeft) || 0;
      return { left: iRect.left - cRect.left - pl, width: iRect.width };
    }

    function setPos(left, width) {
      indicator.style.left = left + 'px';
      indicator.style.width = width + 'px';
    }

    function springTo(tl, tw, iv) {
      const sl = parseFloat(indicator.style.left) || 0;
      const sw = parseFloat(indicator.style.width) || 0;
      const st = performance.now();
      const dur = 450;
      indicator.classList.remove('dragging','drag-fast-right','drag-fast-left');
      indicator.classList.add(iv >= 0 ? 'moving-right' : 'moving-left');
      (function anim(now) {
        const t = Math.min((now - st) / dur, 1);
        const e = 1 - Math.pow(1 - t, 3) * (1 + 3*t + 3*t*t);
        setPos(sl + (tl - sl) * e, sw + (tw - sw) * e);
        if (t < 1) requestAnimationFrame(anim);
        else { setPos(tl, tw); indicator.classList.remove('moving-right','moving-left'); }
      })(performance.now());
    }

    function nearest(centerX) {
      const c = indicator.parentElement;
      if (!c) return currentIndex;
      const cr = c.getBoundingClientRect();
      const pl = parseFloat(getComputedStyle(c).paddingLeft) || 0;
      const rc = centerX - cr.left - pl;
      let ni = 0, md = Infinity;
      items.forEach((it, i) => {
        const ir = it.getBoundingClientRect();
        const ic = ir.left - cr.left - pl + ir.width / 2;
        const d = Math.abs(rc - ic);
        if (d < md) { md = d; ni = i; }
      });
      return ni;
    }

    function proj(v) { return (v/1000)*0.998/(1-0.998); }
    function rb(os, dim, c=0.55) { return (os*dim*c)/(dim+c*Math.abs(os)); }

    indicator.addEventListener('pointerdown', function(e) {
      e.preventDefault(); e.stopPropagation();
      isDragging = true; startX = e.clientX; lastX = e.clientX;
      lastTime = performance.now(); velocity = 0;
      startLeft = parseFloat(indicator.style.left) || 0;
      indicator.classList.add('dragging','pressed');
      try { indicator.setPointerCapture(e.pointerId); } catch(err){}
      currentIndex = getActiveIndex ? getActiveIndex() : currentIndex;
    });

    indicator.addEventListener('pointermove', function(e) {
      if (!isDragging) return;
      const now = performance.now();
      const dt = now - lastTime;
      if (dt > 0) velocity = (e.clientX - lastX) / dt * 1000;
      lastX = e.clientX; lastTime = now;
      let nl = startLeft + (e.clientX - startX);
      const c = indicator.parentElement;
      if (c) {
        const fp = getPos(0), lp = getPos(items.length - 1);
        if (nl < fp.left) nl = fp.left - rb(fp.left - nl, c.offsetWidth);
        else if (nl > lp.left) nl = lp.left + rb(nl - lp.left, c.offsetWidth);
      }
      indicator.classList.remove('drag-fast-right','drag-fast-left');
      if (Math.abs(velocity) > 300)
        indicator.classList.add(velocity > 0 ? 'drag-fast-right' : 'drag-fast-left');
      setPos(nl, parseFloat(indicator.style.width) || 0);
    });

    function end(e) {
      if (!isDragging) return;
      isDragging = false;
      indicator.classList.remove('dragging','pressed','drag-fast-right','drag-fast-left');
      try { indicator.releasePointerCapture(e.pointerId); } catch(err){}
      const pd = proj(velocity);
      const cc = parseFloat(indicator.style.left) + parseFloat(indicator.style.width)/2 + pd;
      const ti = nearest(cc + indicator.parentElement.getBoundingClientRect().left);
      if (ti !== currentIndex || Math.abs(velocity) > 50) {
        const tp = getPos(ti);
        springTo(tp.left, tp.width, velocity);
        if (onSelect) setTimeout(() => onSelect(ti), 50);
        currentIndex = ti;
      } else {
        const cp = getPos(currentIndex);
        springTo(cp.left, cp.width, 0);
      }
    }
    indicator.addEventListener('pointerup', end);
    indicator.addEventListener('pointercancel', end);

    window.addEventListener('resize', () => {
      if (!isDragging) { const p = getPos(currentIndex); setPos(p.left, p.width); }
    });

    return {
      setIndex: function(i) {
        currentIndex = i;
        const p = getPos(i);
        springTo(p.left, p.width, 0);
      },
      getIndex: () => currentIndex,
      refresh: function() {
        const p = getPos(currentIndex);
        setPos(p.left, p.width);
      }
    };
  }


  // ============================================================
  // 顶部 Tab 栏
  // ============================================================
  let tabDrag = null;
  function initTab() {
    const nav = document.getElementById('tabNav');
    if (!nav || initializedContainers.has(nav)) return;
    initializedContainers.add(nav);

    let ind = nav.querySelector('.tab-indicator');
    if (!ind) { ind = document.createElement('div'); ind.className = 'tab-indicator'; nav.insertBefore(ind, nav.firstChild); }

    const tabs = nav.querySelectorAll('.tab-btn');
    if (!tabs.length) return;

    const getActive = () => Array.from(tabs).findIndex(t => t.classList.contains('active'));

    // 延迟定位，确保渲染完成
    setTimeout(() => {
      const ai = getActive();
      if (ai >= 0) {
        const nr = nav.getBoundingClientRect();
        const tr = tabs[ai].getBoundingClientRect();
        ind.style.left = (tr.left - nr.left) + 'px';
        ind.style.width = tr.width + 'px';
        console.log('✅ Tab 滑块定位: left=' + (tr.left - nr.left) + ', width=' + tr.width);
      }
    }, 100);

    tabDrag = makeDraggable(ind, tabs, function(i) {
      tabs.forEach(t => t.classList.remove('active'));
      tabs[i].classList.add('active');
      tabs[i].click();
    }, getActive);

    tabs.forEach((tab, i) => {
      tab.addEventListener('click', () => { if (tabDrag) tabDrag.setIndex(i); });
    });

    console.log('✅ Tab 栏液态玻璃滑块已初始化，共 ' + tabs.length + ' 个标签');
  }


  // ============================================================
  // 批量等级按钮
  // ============================================================
  function initBatch() {
    const btns = document.querySelectorAll('.grade-batch-btn:not([data-lg-init])');
    if (!btns.length) return;

    // 按父容器分组
    const groups = new Map();
    btns.forEach(btn => {
      const p = btn.parentElement;
      if (!groups.has(p)) groups.set(p, []);
      groups.get(p).push(btn);
    });

    groups.forEach((groupBtns, container) => {
      if (initializedContainers.has(container)) return;
      if (groupBtns.length < 2) return;

      initializedContainers.add(container);
      groupBtns.forEach(b => b.setAttribute('data-lg-init', 'true'));

      // 创建 wrapper
      const wrap = document.createElement('div');
      wrap.className = 'grade-batch-container';
      wrap.style.cssText = 'display:inline-flex;align-items:center;gap:4px;';

      const ind = document.createElement('div');
      ind.className = 'grade-batch-indicator';
      wrap.appendChild(ind);

      groupBtns.forEach(b => wrap.appendChild(b));
      container.appendChild(wrap);

      const getActive = () => Array.from(groupBtns).findIndex(b => b.classList.contains('active'));

      setTimeout(() => {
        const ai = getActive();
        if (ai >= 0) {
          const wr = wrap.getBoundingClientRect();
          const br = groupBtns[ai].getBoundingClientRect();
          const pl = parseFloat(getComputedStyle(wrap).paddingLeft) || 0;
          ind.style.left = (br.left - wr.left - pl) + 'px';
          ind.style.width = br.width + 'px';
          ind.style.opacity = '1';
          updateColor(ind, groupBtns[ai].dataset.grade);
          console.log('✅ 批量等级滑块定位: left=' + (br.left - wr.left - pl) + ', width=' + br.width);
        } else {
          ind.style.width = '0px';
          ind.style.opacity = '0';
        }
      }, 150);

      const drag = makeDraggable(ind, groupBtns, function(i) {
        groupBtns.forEach(b => b.classList.remove('active'));
        groupBtns[i].classList.add('active');
        updateColor(ind, groupBtns[i].dataset.grade);
        groupBtns[i].click();
      }, getActive);

      groupBtns.forEach((btn, i) => {
        btn.addEventListener('click', () => {
          if (drag) drag.setIndex(i);
          updateColor(ind, btn.dataset.grade);
        });
      });

      wrap._ind = ind; wrap._drag = drag;
      console.log('✅ 批量等级液态玻璃滑块已初始化，共 ' + groupBtns.length + ' 个按钮');
    });
  }


  // ============================================================
  // 学生行内等级按钮（关键修复：简化容器查找）
  // ============================================================
  function initQuick() {
    const btns = document.querySelectorAll('.grade-qbtn:not([data-lg-init])');
    if (!btns.length) {
      console.log('⚠️ 未找到 .grade-qbtn 元素');
      return;
    }

    console.log('🔍 找到 ' + btns.length + ' 个 .grade-qbtn 元素');

    // 按最近的共同父容器分组
    // 策略：找到每个按钮的 parentElement，如果同一 parent 下有 >=2 个 .grade-qbtn，就用它
    const groups = new Map();
    btns.forEach(btn => {
      // 直接用 parentElement（等级按钮通常在同一个容器里）
      let p = btn.parentElement;
      // 如果 parent 里的 .grade-qbtn 少于 2 个，向上找
      let tries = 0;
      while (p && p.querySelectorAll('.grade-qbtn').length < 2 && tries < 5) {
        p = p.parentElement;
        tries++;
      }
      if (!p) p = btn.parentElement;

      if (!groups.has(p)) groups.set(p, []);
      groups.get(p).push(btn);
    });

    console.log('🔍 分为 ' + groups.size + ' 个组');

    let initCount = 0;
    groups.forEach((groupBtns, container) => {
      if (initializedContainers.has(container)) return;
      if (groupBtns.length < 2) return;

      initializedContainers.add(container);
      groupBtns.forEach(b => b.setAttribute('data-lg-init', 'true'));

      // 确保容器有 position: relative
      container.classList.add('grade-quick-select');
      if (getComputedStyle(container).position === 'static') {
        container.style.position = 'relative';
      }

      // 创建滑块（插入到容器最前面）
      const ind = document.createElement('div');
      ind.className = 'grade-quick-indicator';
      container.insertBefore(ind, container.firstChild);

      const getActive = () => Array.from(groupBtns).findIndex(b => b.classList.contains('active'));

      // 延迟定位（确保渲染完成）
      setTimeout(() => {
        const ai = getActive();
        if (ai >= 0) {
          const cr = container.getBoundingClientRect();
          const br = groupBtns[ai].getBoundingClientRect();
          const pl = parseFloat(getComputedStyle(container).paddingLeft) || 0;
          const left = br.left - cr.left - pl;
          ind.style.left = left + 'px';
          ind.style.width = br.width + 'px';
          ind.style.opacity = '1';
          updateColor(ind, groupBtns[ai].dataset.grade);
          console.log('✅ 学生行内滑块定位: left=' + left + ', width=' + br.width + ', grade=' + groupBtns[ai].dataset.grade);
        } else {
          // 即使没有 active，也定位到第一个按钮
          const cr = container.getBoundingClientRect();
          const br = groupBtns[0].getBoundingClientRect();
          const pl = parseFloat(getComputedStyle(container).paddingLeft) || 0;
          ind.style.left = (br.left - cr.left - pl) + 'px';
          ind.style.width = br.width + 'px';
          ind.style.opacity = '0.3';
          console.log('ℹ️ 学生行内无 active，定位到第一个按钮');
        }
      }, 200);

      const drag = makeDraggable(ind, groupBtns, function(i) {
        groupBtns.forEach(b => b.classList.remove('active'));
        groupBtns[i].classList.add('active');
        updateColor(ind, groupBtns[i].dataset.grade);
        groupBtns[i].click();
      }, getActive);

      groupBtns.forEach((btn, i) => {
        btn.addEventListener('click', () => {
          if (drag) drag.setIndex(i);
          updateColor(ind, btn.dataset.grade);
        });
      });

      container._ind = ind; container._drag = drag;
      initCount++;
    });

    if (initCount > 0) console.log('✅ 学生行内等级液态玻璃滑块已初始化，共 ' + initCount + ' 组');
  }


  // ============================================================
  // 工具函数
  // ============================================================
  function updateColor(ind, grade) {
    if (!ind) return;
    ind.classList.remove('grade-A','grade-B','grade-C','grade-other');
    if (grade === 'A') ind.classList.add('grade-A');
    else if (grade === 'B') ind.classList.add('grade-B');
    else if (grade === 'C') ind.classList.add('grade-C');
    else ind.classList.add('grade-other');
  }

  window.refreshLGS = function() { initBatch(); initQuick(); };


  // ============================================================
  // 初始化
  // ============================================================
  function init() {
    initTab();
    initBatch();
    initQuick();
  }

  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', init);
  else init();

  // 多次尝试初始化（学生行是异步生成的）
  [300, 800, 1500, 2500, 4000].forEach(function(delay) {
    setTimeout(function() {
      initBatch();
      initQuick();
      console.log('🔄 延迟初始化尝试: ' + delay + 'ms');
    }, delay);
  });

  // 监听 DOM 变化（关键：学生行是动态生成的）
  var domTimer = null;
  new MutationObserver(function() {
    if (domTimer) clearTimeout(domTimer);
    domTimer = setTimeout(function() { initBatch(); initQuick(); }, 200);
  }).observe(document.body, { subtree: true, childList: true, characterData: true });

  // 定期检查（兜底机制）
  setInterval(function() {
    var uninitBtns = document.querySelectorAll('.grade-qbtn:not([data-lg-init])');
    if (uninitBtns.length > 0) {
      console.log('🔍 定期检查发现 ' + uninitBtns.length + ' 个未初始化的 .grade-qbtn');
      initQuick();
    }
    var uninitBatch = document.querySelectorAll('.grade-batch-btn:not([data-lg-init])');
    if (uninitBatch.length > 0) {
      console.log('🔍 定期检查发现 ' + uninitBatch.length + ' 个未初始化的 .grade-batch-btn');
      initBatch();
    }
  }, 1000);

  console.log('✅ 液态玻璃滑块效果已加载（高保真版 + 可靠初始化）');

})();
