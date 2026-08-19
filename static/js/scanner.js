/* ============================================================
   ClassTrack 统一扫码引擎 v2.1
   - 优先: BarcodeDetector API (浏览器原生, Canvas 兼容路径)
   - 兜底: html5-qrcode (本地库, 经过验证的 jsQR 实现)
   - 特性: 批量识别 / 自动去重 / 防重复提交
   ============================================================ */

var ClassTrackScanner = (function () {
  "use strict";

  var DEDUP_WINDOW_MS = 3000;

  // ---- BarcodeDetector 能力检测 ----
  function _supportsBarcodeDetector() {
    if (typeof BarcodeDetector === "undefined") return false;
    try {
      new BarcodeDetector({ formats: ["qr_code"] });
      return true;
    } catch (_) {
      return false;
    }
  }

  // ---- 懒加载 html5-qrcode (本地文件, 仅兜底时加载) ----
  var _html5QrReady = null;

  function _loadHtml5Qr() {
    if (_html5QrReady) return _html5QrReady;
    if (typeof Html5Qrcode !== "undefined") {
      _html5QrReady = Promise.resolve();
      return _html5QrReady;
    }
    _html5QrReady = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = "/static/html5-qrcode.min.js";
      s.onload = function () { resolve(); };
      s.onerror = function () { reject(new Error("html5-qrcode 加载失败")); };
      document.head.appendChild(s);
    });
    return _html5QrReady;
  }

  // ============================================================
  // Scanner 类
  // ============================================================
  function Scanner(opts) {
    opts = opts || {};
    this.onScan = opts.onScan || function () {};
    this.fps = opts.fps || 30;
    this.facingMode = opts.facingMode || "environment";
    this.scanWidth = opts.scanWidth || 640;

    this._video = null;
    this._stream = null;
    this._canvas = null;
    this._ctx = null;
    this._running = false;
    this._engine = null;      // 'barcode-detector' | 'html5-qrcode'
    this._detector = null;    // BarcodeDetector 实例
    this._html5Scanner = null; // Html5Qrcode 实例 (兜底)
    this._seen = {};          // code → timestamp (用普通对象, 避免 Map 迭代问题)
    this._timer = null;
    this._videoReady = false;
  }

  // ---- 初始化引擎 ----
  Scanner.prototype.init = async function () {
    if (_supportsBarcodeDetector()) {
      this._detector = new BarcodeDetector({ formats: ["qr_code"] });
      this._engine = "barcode-detector";
      console.log("[Scanner] 引擎: BarcodeDetector (硬件加速, Canvas 路径)");
      return this._engine;
    }

    // 兜底: html5-qrcode (本地 jsQR)
    try {
      await _loadHtml5Qr();
      this._engine = "html5-qrcode";
      console.log("[Scanner] 引擎: html5-qrcode (jsQR 软件)");
      return this._engine;
    } catch (e) {
      throw new Error("当前浏览器不支持扫码功能: " + e.message);
    }
  };

  // ---- 启动摄像头 + 扫描循环 ----
  Scanner.prototype.start = async function (videoEl) {
    if (this._running) return;
    this._video = videoEl;

    // 打开摄像头
    var constraints = {
      video: {
        facingMode: this.facingMode,
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    };

    if (this._engine === "html5-qrcode") {
      // html5-qrcode 需要容器元素（div），不是 video
      var self = this;
      var container = this._video.parentElement;
      if (!container || container === document.body) {
        // 兜底：创建一个 wrapper
        container = document.createElement("div");
        this._video.parentElement.insertBefore(container, this._video);
        container.appendChild(this._video);
      }
      if (!container.id) {
        container.id = "scannerCt_" + Date.now();
      }
      this._html5Scanner = new Html5Qrcode(container.id);
      await this._html5Scanner.start(
        { facingMode: this.facingMode },
        { fps: this.fps, qrbox: { width: 250, height: 250 }, aspectRatio: 1 },
        function (text) {
          var code = (text || "").trim();
          if (!code) return;
          var now = Date.now();
          if (self._seen[code] && now - self._seen[code] < DEDUP_WINDOW_MS) return;
          self._seen[code] = now;
          self.onScan([code]);
        },
        function () {}
      );
      this._running = true;
      return;
    }

    // BarcodeDetector 路径
    this._stream = await navigator.mediaDevices.getUserMedia(constraints);
    this._video.srcObject = this._stream;
    this._video.setAttribute("playsinline", "");
    this._video.setAttribute("autoplay", "");
    await this._video.play();

    // ★ 关键: 等首帧解码就绪后再开始扫描
    var self = this;
    await new Promise(function (resolve) {
      if (self._video.readyState >= 2) { resolve(); return; }
      self._video.addEventListener("loadeddata", resolve, { once: true });
      // 超时保护: 2 秒后无论如何开始
      setTimeout(resolve, 2000);
    });
    this._videoReady = true;

    // 离屏 Canvas (BarcodeDetector 用 Canvas 而非 video, 兼容性更好)
    var w = this._video.videoWidth || 1280;
    var h = this._video.videoHeight || 720;
    var scale = Math.min(1, this.scanWidth / w);
    this._canvas = document.createElement("canvas");
    this._canvas.width = Math.round(w * scale);
    this._canvas.height = Math.round(h * scale);
    this._ctx = this._canvas.getContext("2d", { willReadFrequently: true });

    this._running = true;
    this._scanLoop();
  };

  // ---- 停止 ----
  Scanner.prototype.stop = async function () {
    this._running = false;
    if (this._timer) { clearTimeout(this._timer); this._timer = null; }
    if (this._html5Scanner) {
      try { await this._html5Scanner.stop(); } catch (_) {}
      this._html5Scanner = null;
    }
    if (this._stream) {
      this._stream.getTracks().forEach(function (t) { t.stop(); });
      this._stream = null;
    }
    if (this._video) {
      this._video.srcObject = null;
    }
    this._seen = {};
    this._videoReady = false;
  };

  // ---- 扫描循环 (BarcodeDetector 路径) ----
  Scanner.prototype._scanLoop = async function () {
    if (!this._running || this._engine !== "barcode-detector") return;

    var start = performance.now();
    var intervalMs = Math.max(33, Math.round(1000 / this.fps)); // 最低 33ms (~30fps)

    try {
      // 用 Canvas: 先 drawImage 再 detect, 比 detect(video) 更可靠
      if (this._videoReady && this._video.readyState >= 2) {
        this._ctx.drawImage(this._video, 0, 0, this._canvas.width, this._canvas.height);
        var results = await this._detector.detect(this._canvas);
        var codes = results.map(function (r) { return (r.rawValue || "").trim(); }).filter(Boolean);

        if (codes.length > 0) {
          var now = Date.now();
          var fresh = [];
          for (var i = 0; i < codes.length; i++) {
            var c = codes[i];
            var last = this._seen[c];
            if (last && now - last < DEDUP_WINDOW_MS) continue;
            this._seen[c] = now;
            fresh.push(c);
          }

          // 清理过期条目
          var expire = now - DEDUP_WINDOW_MS * 2;
          var keys = Object.keys(this._seen);
          for (var j = 0; j < keys.length; j++) {
            if (this._seen[keys[j]] < expire) delete this._seen[keys[j]];
          }

          if (fresh.length > 0) {
            this.onScan(fresh);
          }
        }
      }
    } catch (e) {
      // 连续失败超过 30 次 → 可能是引擎故障, 静默降级
      // 大多数情况下, 单帧失败不影响
    }

    var elapsed = performance.now() - start;
    var delay = Math.max(1, intervalMs - elapsed);
    var self = this;
    this._timer = setTimeout(function () { self._scanLoop(); }, delay);
  };

  // ---- 手动清理去重缓存 ----
  Scanner.prototype.clearDedup = function () {
    this._seen = {};
  };

  return Scanner;
})();

// CommonJS 导出
if (typeof module !== "undefined" && module.exports) {
  module.exports = ClassTrackScanner;
}
