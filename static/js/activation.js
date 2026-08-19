/* ============================================================
   ClassTrack Activation Page — 激活登录页逻辑
   ============================================================
   全程离线，纯本地运算
   主流程：粘贴密钥 → 验证激活
   备选流程：导入激活文件 / 拖拽文件
   动画复用全局 iOS 缓动曲线参数
   ============================================================ */

(function () {
  "use strict";

  // ============================================================
  // DOM 引用
  // ============================================================
  const overlay = document.getElementById("activationOverlay");
  const card = document.getElementById("activationCard");
  const statusMsg = document.getElementById("activationStatusMsg");
  const machineCodeEl = document.getElementById("machineCode");
  const btnCopyCode = document.getElementById("btnCopyCode");
  const btnCopyLabel = document.getElementById("btnCopyLabel");
  const keyInput = document.getElementById("activationKeyInput");
  const btnVerify = document.getElementById("btnVerify");
  const btnExportFp = document.getElementById("btnExportFingerprint");
  const fileInput = document.getElementById("activationFileInput");

  // ============================================================
  // 状态
  // ============================================================
  let machineCode = "";
  let fingerprintExport = "";
  let isVerifying = false;

  // ============================================================
  // 状态提示更新
  // ============================================================
  function setStatus(text, type) {
    statusMsg.textContent = text;
    statusMsg.className = "activation-status-msg " + type;
  }

  // ============================================================
  // 初始化：获取本机机器码
  // ============================================================
  async function initMachineCode() {
    try {
      const resp = await fetch("/api/activation/fingerprint");
      const data = await resp.json();
      if (data.code === 0) {
        machineCode = data.data.machine_code;
        fingerprintExport = data.data.fingerprint_export;
        machineCodeEl.textContent = machineCode;
      } else {
        machineCodeEl.textContent = "采集失败";
        setStatus("⚠️ 硬件指纹采集失败，请重启软件重试", "error");
      }
    } catch (err) {
      machineCodeEl.textContent = "采集失败";
      setStatus("⚠️ 无法连接本地服务", "error");
    }
  }

  // ============================================================
  // 核心：发送密钥内容到后端校验
  // ============================================================
  async function verifyKeyContent(content) {
    if (isVerifying) return;
    isVerifying = true;
    btnVerify.disabled = true;
    setStatus("⏳ 正在校验激活密钥...", "verifying");

    try {
      const resp = await fetch("/api/activation/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_content: content }),
      });
      const data = await resp.json();

      if (data.code === 0 && data.data.activated) {
        setStatus("✅ 激活成功！正在进入系统...", "success");
        keyInput.disabled = true;
        btnVerify.style.display = "none";
        setTimeout(performExitAnimation, 800);
      } else {
        const reason = data.msg || data.data?.reason || "未知错误";
        setStatus("❌ " + reason, "error");
      }
    } catch (err) {
      setStatus("❌ 校验请求失败，请重试", "error");
    } finally {
      isVerifying = false;
      btnVerify.disabled = false;
    }
  }

  // ============================================================
  // 粘贴密钥 → 点击验证
  // ============================================================
  btnVerify.addEventListener("click", () => {
    const content = keyInput.value.trim();
    if (!content) {
      setStatus("⚠️ 请先粘贴商家提供的激活密钥", "error");
      keyInput.focus();
      return;
    }
    verifyKeyContent(content);
  });

  // 支持 Ctrl+Enter 快捷验证
  keyInput.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      btnVerify.click();
    }
  });

  // 粘贴时自动去除首尾空白和引号
  keyInput.addEventListener("paste", () => {
    setTimeout(() => {
      let val = keyInput.value;
      // 自动去除可能误粘贴的引号
      val = val.replace(/^["']|["']$/g, "").trim();
      keyInput.value = val;
    }, 50);
  });

  // ============================================================
  // 一键复制机器码
  // ============================================================
  btnCopyCode.addEventListener("click", async () => {
    if (!machineCode || machineCode === "正在采集...") return;
    try {
      await navigator.clipboard.writeText(machineCode);
      btnCopyLabel.textContent = "已复制 ✓";
      btnCopyCode.classList.add("copied");
      setTimeout(() => {
        btnCopyLabel.textContent = "复制";
        btnCopyCode.classList.remove("copied");
      }, 2000);
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(machineCodeEl);
      selection.removeAllRanges();
      selection.addRange(range);
      btnCopyLabel.textContent = "已选中";
      setTimeout(() => { btnCopyLabel.textContent = "复制"; }, 1500);
    }
  });

  // ============================================================
  // 复制机器指纹（发送给商家）
  // ============================================================
  btnExportFp.addEventListener("click", async () => {
    if (!fingerprintExport) {
      setStatus("⚠️ 机器指纹尚未就绪，请稍候重试", "error");
      return;
    }
    try {
      await navigator.clipboard.writeText(fingerprintExport);
      const origHTML = btnExportFp.innerHTML;
      btnExportFp.innerHTML = "<span>✅</span><span>指纹已复制，请发送给商家</span>";
      setTimeout(() => { btnExportFp.innerHTML = origHTML; }, 2500);
    } catch {
      setStatus("⚠️ 复制失败，请手动选中机器码发送", "error");
    }
  });

  // ============================================================
  // 文件导入（备选方式）
  // ============================================================
  fileInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const fileContent = await file.text();
      // 将文件内容填入输入框，让用户确认后再点击验证
      keyInput.value = fileContent;
      setStatus("📂 已读取文件内容，请点击「验证激活」确认", "locked");
    } catch (err) {
      setStatus("❌ 文件读取失败，请改用粘贴密钥方式", "error");
    }
    fileInput.value = "";
  });

  // ============================================================
  // 拖拽 .dat 文件直接激活（备选方式）
  // ============================================================
  document.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.stopPropagation();
    card.style.boxShadow = "0 0 30px rgba(126, 181, 214, 0.30)";
  });

  document.addEventListener("dragleave", (e) => {
    e.preventDefault();
    e.stopPropagation();
    card.style.boxShadow = "";
  });

  document.addEventListener("drop", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    card.style.boxShadow = "";

    const file = e.dataTransfer.files[0];
    if (!file) return;

    try {
      const fileContent = await file.text();
      // 拖拽文件直接验证
      await verifyKeyContent(fileContent);
    } catch (err) {
      setStatus("❌ 文件读取失败，请改用粘贴密钥方式", "error");
    }
  });

  // ============================================================
  // 退场动画 + 跳转主界面
  // ============================================================
  function performExitAnimation() {
    keyInput.disabled = true;
    btnVerify.style.pointerEvents = "none";
    btnVerify.style.opacity = "0.6";

    card.style.transition = "box-shadow 0.35s cubic-bezier(0.23, 1, 0.32, 1)";
    card.style.boxShadow = "0 0 36px rgba(168, 213, 186, 0.35)";

    setTimeout(() => {
      overlay.classList.add("exit-animation");

      overlay.addEventListener("animationend", () => {
        window.location.href = "/";
      }, { once: true });

      // 兜底：650ms 后强制跳转
      setTimeout(() => {
        window.location.href = "/";
      }, 650);
    }, 400);
  }

  // ============================================================
  // 特效开关检测（复用主程序设置）
  // ============================================================
  function checkGlassDisabled() {
    try {
      const stored = localStorage.getItem("classtrack_glass_disabled");
      if (stored === "true") {
        document.body.classList.add("glass-disabled");
      }
    } catch {
      // localStorage 不可用，忽略
    }
  }

  // ============================================================
  // 启动
  // ============================================================
  checkGlassDisabled();
  initMachineCode();
})();
