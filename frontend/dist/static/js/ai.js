/* ============================================================
   ClassTrack v2.0 — AI 助手前端模块
   涵盖：设置 / 对话 / 评语 / 预警 / 智能分组
   设计原则：任何错误都不影响原有功能
   ============================================================ */
(function () {
  "use strict";

  // ============================================================
  // AI 全局状态（挂到 window 以便 app.js 可访问）
  // ============================================================
  const AIState = {
    config: null,
    chatHistory: [],
    currentChart: null,
    alerts: [],
    smartGroupResult: null,
  };
  window.AIState = AIState;

  // ECharts 是否可用
  let echartsReady = false;

  // ============================================================
  // 安全初始化：所有错误都被捕获，不影响原有功能
  // ============================================================
  function safeInit() {
    try { setupSettingsTab(); } catch (e) { console.warn("AI settings init failed:", e.message); }
    try { setupAIChatTab(); } catch (e) { console.warn("AI chat init failed:", e.message); }
    try { setupAlertBanner(); } catch (e) { console.warn("AI alerts init failed:", e.message); }
    try { setupAICommentButton(); } catch (e) { console.warn("AI comment init failed:", e.message); }
    try { setupSmartGroupButton(); } catch (e) { console.warn("AI smart group init failed:", e.message); }
  }

  // ============================================================
  // Tab 5: ⚙️ 设置
  // ============================================================
  function setupSettingsTab() {
    var providerSelect = document.getElementById("aiProvider");
    var apiKeyInput = document.getElementById("aiApiKey");
    var baseUrlInput = document.getElementById("aiBaseUrl");
    var modelInput = document.getElementById("aiModel");
    var testBtn = document.getElementById("btnAITest");
    var saveBtn = document.getElementById("btnAISave");
    var statusEl = document.getElementById("aiSettingsStatus");

    if (!providerSelect || !saveBtn) return;

    var defaults = {
      deepseek: { url: "https://api.deepseek.com/v1", model: "deepseek-chat" },
      openai: { url: "https://api.openai.com/v1", model: "gpt-3.5-turbo" },
      qwen: { url: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-plus" },
      custom: { url: "", model: "" },
    };

    providerSelect.addEventListener("change", function () {
      var v = providerSelect.value;
      var d = defaults[v] || { url: "", model: "" };
      if (v !== "custom") {
        if (baseUrlInput) baseUrlInput.value = d.url;
        if (modelInput) modelInput.value = d.model;
      }
    });

    loadAIConfig();

    if (testBtn) {
      testBtn.addEventListener("click", async function () {
        testBtn.disabled = true;
        testBtn.textContent = "⏳ 测试中...";
        if (statusEl) { statusEl.className = "settings-status"; statusEl.innerHTML = ""; }
        try {
          var resp = await fetch("/api/ai/test", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              provider: providerSelect.value,
              api_key: apiKeyInput ? apiKeyInput.value : "",
              base_url: baseUrlInput ? baseUrlInput.value : "",
              model: modelInput ? modelInput.value : "",
            }),
          });
          var data = await resp.json();
          if (statusEl) {
            if (data.code === 0) {
              statusEl.className = "settings-status success";
              statusEl.innerHTML = "🟢 连接成功！API 服务正常";
            } else {
              statusEl.className = "settings-status error";
              statusEl.innerHTML = "🔴 " + data.msg;
            }
          }
        } catch (e) {
          if (statusEl) {
            statusEl.className = "settings-status error";
            statusEl.innerHTML = "🔴 网络请求失败，请检查网络连接";
          }
        }
        testBtn.disabled = false;
        testBtn.textContent = "🔌 测试连接";
      });
    }

    if (saveBtn) {
      saveBtn.addEventListener("click", async function () {
        var apiKey = apiKeyInput ? apiKeyInput.value.trim() : "";
        if (!apiKey) {
          if (statusEl) { statusEl.className = "settings-status error"; statusEl.innerHTML = "🔴 请输入 API Key"; }
          return;
        }
        saveBtn.disabled = true;
        saveBtn.textContent = "⏳ 保存中...";
        try {
          var resp = await fetch("/api/ai/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              provider: providerSelect.value,
              api_key: apiKey,
              base_url: baseUrlInput ? baseUrlInput.value.trim() : "",
              model: modelInput ? modelInput.value.trim() : "",
            }),
          });
          var data = await resp.json();
          if (statusEl) {
            if (data.code === 0) {
              statusEl.className = "settings-status success";
              statusEl.innerHTML = "✅ 配置已保存";
              if (typeof showToast === "function") showToast("✅ AI 配置已保存");
            } else {
              statusEl.className = "settings-status error";
              statusEl.innerHTML = "🔴 " + data.msg;
            }
          }
        } catch (e) {
          if (statusEl) {
            statusEl.className = "settings-status error";
            statusEl.innerHTML = "🔴 保存失败，请重试";
          }
        }
        saveBtn.disabled = false;
        saveBtn.textContent = "💾 保存配置";
      });
    }
  }

  async function loadAIConfig() {
    try {
      var resp = await fetch("/api/ai/config");
      var data = await resp.json();
      if (data.code === 0) {
        AIState.config = data.data;
        var el = document.getElementById("aiProvider");
        if (el) el.value = data.data.provider || "deepseek";
        var keyEl = document.getElementById("aiApiKey");
        if (keyEl && data.data.has_key) {
          keyEl.placeholder = "已保存 (" + data.data.api_key_masked + ")";
        }
        var urlEl = document.getElementById("aiBaseUrl");
        if (urlEl && !data.data.base_url) {
          // trigger default
          if (el) el.dispatchEvent(new Event("change"));
        } else if (urlEl) {
          urlEl.value = data.data.base_url || "";
        }
        var modelEl = document.getElementById("aiModel");
        if (modelEl) modelEl.value = data.data.model || "";
      }
    } catch (e) {
      console.log("AI config load failed:", e.message);
    }
  }
  window.loadAIConfig = loadAIConfig;

  // ============================================================
  // Tab 6: 🤖 AI 助手
  // ============================================================
  // ---- 考试 Excel 上传和处理 ----
  function setupExamUpload() {
    var uploadBtn = document.getElementById("btnUploadExam");
    var fileInput = document.getElementById("examFileInput");
    var examBar = document.getElementById("aiExamBar");
    var examInfo = document.getElementById("aiExamInfo");
    var clearBtn = document.getElementById("btnClearExam");
    var applyBtn = document.getElementById("btnApplyExam");

    if (!uploadBtn || !fileInput) return;

    // 点击上传按钮
    uploadBtn.addEventListener("click", function () {
      fileInput.click();
    });

    // 文件选择
    fileInput.addEventListener("change", async function () {
      var file = fileInput.files[0];
      if (!file) return;

      uploadBtn.style.opacity = "0.5";
      uploadBtn.title = "上传中...";

      var formData = new FormData();
      formData.append("file", file);

      try {
        var resp = await fetch("/api/ai/import-exam", {
          method: "POST",
          body: formData,
        });
        var data = await resp.json();

        if (data.code === 0) {
          if (typeof showToast === "function") showToast("✅ " + data.msg);
          showExamPreview(data.data);
          updateExamBar(data.data);
        } else {
          if (typeof showToast === "function") showToast("❌ " + data.msg);
        }
      } catch (e) {
        if (typeof showToast === "function") showToast("❌ 上传失败，请检查网络");
      }

      uploadBtn.style.opacity = "1";
      uploadBtn.title = "上传考试 Excel";
      fileInput.value = "";
    });

    // 清除考试数据
    if (clearBtn) {
      clearBtn.addEventListener("click", async function () {
        await fetch("/api/ai/exam-data/clear", { method: "POST" });
        if (examBar) examBar.style.display = "none";
        if (typeof showToast === "function") showToast("🗑 考试数据已清除");
      });
    }

    // 应用成绩登记
    if (applyBtn) {
      applyBtn.addEventListener("click", function () {
        showExamApplyModal();
      });
    }

    // 页面加载时检查是否有缓存数据
    checkExistingExamData();
  }

  async function checkExistingExamData() {
    try {
      var resp = await fetch("/api/ai/exam-data");
      var data = await resp.json();
      if (data.code === 0 && data.data && data.data.data) {
        updateExamBar(data.data.data);
      }
    } catch (e) { /* ignore */ }
  }

  function updateExamBar(examData) {
    var bar = document.getElementById("aiExamBar");
    var info = document.getElementById("aiExamInfo");
    if (!bar || !info) return;

    var classNames = examData.classes.map(function (c) { return c.class_name; }).join(", ");
    info.textContent = "📋 " + examData.total_students + "人 · " + classNames;
    bar.style.display = "flex";
  }

  function showExamPreview(examData) {
    var modal = document.getElementById("examPreviewModal");
    if (!modal) {
      modal = document.createElement("div");
      modal.className = "modal-overlay";
      modal.id = "examPreviewModal";
      modal.innerHTML =
        '<div class="modal-card modal-wide">' +
        '<div class="modal-header"><h3>📋 考试数据预览</h3><button class="modal-close" id="btnExamPreviewClose">✕</button></div>' +
        '<div class="modal-body"><div id="examPreviewContent"></div>' +
        '<div style="margin-top:12px;display:flex;gap:8px">' +
        '<button class="btn btn-primary" id="btnExamApplyNow">✅ 登记成绩到系统</button>' +
        '<span style="font-size:.78rem;color:var(--text-light);margin-left:auto;display:flex;align-items:center">💡 登记后可在 AI 对话中提问分析</span>' +
        '</div></div></div>';
      document.body.appendChild(modal);

      modal.querySelector("#btnExamPreviewClose").addEventListener("click", function () {
        modal.style.display = "none";
      });
      modal.addEventListener("click", function (e) {
        if (e.target === modal) modal.style.display = "none";
      });
      modal.querySelector("#btnExamApplyNow").addEventListener("click", function () {
        modal.style.display = "none";
        showExamApplyModal();
      });
    }

    var content = modal.querySelector("#examPreviewContent");
    var html = '<div style="margin-bottom:8px;color:var(--text-light);font-size:.82rem">' +
      '已识别 <strong>' + examData.total_students + '</strong> 名学生，' +
      '<strong>' + examData.classes.length + '</strong> 个班级/组别 · ' +
      '识别列: ' + (examData.detected_columns || []).join(", ") + '</div>';

    for (var i = 0; i < examData.classes.length; i++) {
      var cls = examData.classes[i];
      var st = cls.stats || {};
      html += '<div class="exam-preview-class">' +
        '<div class="exam-preview-class-header">' +
        '<span>📊</span> ' + cls.class_name +
        '<span style="font-weight:400;font-size:.78rem;margin-left:auto">' + cls.student_count + '人 · 均分 ' + cls.avg_score + ' · 最高 ' + cls.max_score + ' · 最低 ' + cls.min_score + '</span>' +
        '</div>' +
        '<div class="exam-preview-class-body">' +
        '<div class="exam-preview-stats">' +
        '<span>⭐ A(≥90): ' + (st.A || 0) + '人</span>' +
        '<span>🔵 B(≥75): ' + (st.B || 0) + '人</span>' +
        '<span>🟡 C(≥60): ' + (st.C || 0) + '人</span>' +
        '<span>🔴 未达标: ' + (st.X || 0) + '人</span>' +
        '</div>' +
        '<table style="width:100%;font-size:.78rem;border-collapse:collapse">' +
        '<tr style="border-bottom:1px solid #eee"><th style="text-align:left;padding:4px">姓名</th><th>学号</th><th>分数</th><th>等第</th></tr>';

      var students = cls.students || [];
      var showCount = Math.min(students.length, 15);
      for (var j = 0; j < showCount; j++) {
        var s = students[j];
        var gColor = s.grade === "A" ? "#7EB5D6" : s.grade === "B" ? "#A8D5BA" : s.grade === "C" ? "#F4C97E" : s.grade === "L" ? "#C5B3E6" : "#E8A0BF";
        var gLabel = s.grade === "X" ? "未交" : s.grade === "L" ? "请假" : s.grade;
        html += '<tr><td style="padding:3px 4px">' + s.name + '</td>' +
          '<td style="color:var(--text-light)">' + (s.code || "-") + '</td>' +
          '<td>' + (s.score_display || "-") + '</td>' +
          '<td><span style="background:' + gColor + ';color:#fff;padding:1px 6px;border-radius:8px;font-size:.7rem;font-weight:600">' + gLabel + '</span></td></tr>';
      }
      if (students.length > showCount) {
        html += '<tr><td colspan="4" style="text-align:center;color:var(--text-lighter);padding:4px">... 还有 ' + (students.length - showCount) + ' 名学生</td></tr>';
      }
      html += '</table></div></div>';
    }
    content.innerHTML = html;
    modal.style.display = "flex";
  }

  function showExamApplyModal() {
    var modal = document.getElementById("examApplyModal");
    if (!modal) {
      modal = document.createElement("div");
      modal.className = "modal-overlay";
      modal.id = "examApplyModal";
      modal.innerHTML =
        '<div class="modal-card">' +
        '<div class="modal-header"><h3>✅ 登记考试成绩</h3><button class="modal-close" id="btnExamApplyClose">✕</button></div>' +
        '<div class="modal-body">' +
        '<p style="font-size:.85rem;color:var(--text-light);margin-bottom:12px">系统将根据学号或姓名自动匹配学生，将考试等第登记到作业记录中。</p>' +
        '<div class="settings-row"><label>登记日期</label><input type="date" id="examApplyDate"></div>' +
        '<div class="settings-row"><label>目标班级</label><select id="examApplyClass"><option value="">全部班级</option></select></div>' +
        '<div class="settings-row"><label>作业种类</label><select id="examApplyType"></select></div>' +
        '<div style="display:flex;gap:8px;margin-top:14px">' +
        '<button class="btn btn-primary" id="btnExamApplyConfirm">✅ 确认登记</button>' +
        '<span id="examApplyStatus" style="font-size:.78rem;color:var(--text-light);display:flex;align-items:center"></span>' +
        '</div></div></div>';
      document.body.appendChild(modal);

      modal.querySelector("#btnExamApplyClose").addEventListener("click", function () {
        modal.style.display = "none";
      });
      modal.addEventListener("click", function (e) {
        if (e.target === modal) modal.style.display = "none";
      });

      modal.querySelector("#btnExamApplyConfirm").addEventListener("click", async function () {
        var date = document.getElementById("examApplyDate").value;
        var className = document.getElementById("examApplyClass").value;
        var hwTypeId = document.getElementById("examApplyType").value;
        var statusEl = document.getElementById("examApplyStatus");

        var btn = modal.querySelector("#btnExamApplyConfirm");
        btn.disabled = true;
        btn.textContent = "⏳ 登记中...";
        statusEl.textContent = "";

        try {
          var resp = await fetch("/api/ai/import-exam/apply", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              date: date,
              class_name: className,
              homework_type_id: parseInt(hwTypeId) || 0,
            }),
          });
          var data = await resp.json();
          if (data.code === 0) {
            statusEl.innerHTML = '<span style="color:#2d8a56">✅ ' + data.msg + '</span>';
            if (typeof showToast === "function") showToast("✅ " + data.msg);
            setTimeout(function () { modal.style.display = "none"; }, 1500);
          } else {
            statusEl.innerHTML = '<span style="color:#c0392b">❌ ' + data.msg + '</span>';
          }
        } catch (e) {
          statusEl.innerHTML = '<span style="color:#c0392b">❌ 请求失败</span>';
        }
        btn.disabled = false;
        btn.textContent = "✅ 确认登记";
      });
    }

    // 填充日期
    var dateEl = document.getElementById("examApplyDate");
    if (dateEl) {
      var today = new Date().toISOString().split("T")[0];
      dateEl.value = today;
    }

    // 填充班级选项
    var classEl = document.getElementById("examApplyClass");
    if (classEl && classEl.options.length === 0) {
      fetch("/api/ai/exam-data").then(function (r) { return r.json(); }).then(function (data) {
        if (data.code === 0 && data.data && data.data.data) {
          var classes = data.data.data.classes || [];
          for (var i = 0; i < classes.length; i++) {
            var opt = document.createElement("option");
            opt.value = classes[i].class_name;
            opt.textContent = classes[i].class_name + " (" + classes[i].student_count + "人)";
            classEl.appendChild(opt);
          }
        }
      }).catch(function () {});
    }

    // 填充作业种类
    var typeEl = document.getElementById("examApplyType");
    if (typeEl && typeEl.options.length === 0) {
      fetch("/api/homework-types").then(function (r) { return r.json(); }).then(function (data) {
        if (data.code === 0) {
          for (var i = 0; i < data.data.length; i++) {
            var opt = document.createElement("option");
            opt.value = data.data[i].id;
            opt.textContent = data.data[i].name;
            typeEl.appendChild(opt);
          }
        }
      }).catch(function () {});
    }

    modal.style.display = "flex";
  }

  // ---- 获取当前班级/作业种类 ID（模块级，供多处使用） ----
  function getCurrentClassId() {
    if (window.State && window.State.currentClassId) {
      return window.State.currentClassId;
    }
    return 0;
  }

  function getCurrentHomeworkTypeId() {
    if (window.State && window.State.currentHomeworkTypeId) {
      return window.State.currentHomeworkTypeId;
    }
    return 0;
  }

  // ---- 加载提问建议（模块级，供 resetAIContext 和 setupAIChatTab 共用） ----
  function loadSuggestions() {
    var container = document.getElementById("aiQuickQuestions");
    if (!container) return;
    container.innerHTML = '<span style="color:var(--text-lighter);font-size:.78rem">⏳ 加载建议中...</span>';

    var params = new URLSearchParams();
    var cid = getCurrentClassId();
    if (cid > 0) params.set("class_id", cid);
    var hwTypeId = getCurrentHomeworkTypeId();
    if (hwTypeId > 0) params.set("homework_type_id", hwTypeId);
    var queryStr = params.toString();
    var url = "/api/ai/suggestions" + (queryStr ? "?" + queryStr : "");

    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.code === 0 && data.data.suggestions) {
          var html = "";
          for (var i = 0; i < data.data.suggestions.length; i++) {
            var s = data.data.suggestions[i];
            html += '<button class="ai-quick-btn" data-question="' + s.text.replace(/"/g, "&quot;") + '">' +
              (s.icon || "") + " " + s.text + "</button>";
          }
          container.innerHTML = html;
          // 重新绑定事件
          var btns = container.querySelectorAll(".ai-quick-btn");
          for (var j = 0; j < btns.length; j++) {
            btns[j].addEventListener("click", function () {
              var input = document.getElementById("aiChatInput");
              var sendBtn = document.getElementById("btnAISend");
              if (input && sendBtn) {
                input.value = this.dataset.question;
                sendBtn.click();
              }
            });
          }
        }
      })
      .catch(function () {
        // 加载失败，保留默认按钮
      });
  }

  // ---- 作业种类选择器 ----
  function setupHomeworkTypeSelector() {
    var sel = document.getElementById("aiHomeworkTypeSelect");
    if (!sel) return;

    // 从全局 State 或后端加载作业种类
    function populateTypes() {
      // 优先使用全局 State 中的 homeworkTypes
      if (window.State && window.State.homeworkTypes && window.State.homeworkTypes.length > 0) {
        sel.innerHTML = '<option value="0">全部种类</option>';
        for (var i = 0; i < window.State.homeworkTypes.length; i++) {
          var t = window.State.homeworkTypes[i];
          var selected = (window.State.currentHomeworkTypeId && window.State.currentHomeworkTypeId === t.id) ? " selected" : "";
          sel.innerHTML += '<option value="' + t.id + '"' + selected + '>' + t.name + '</option>';
        }
      } else {
        // 兜底：从 API 加载
        fetch("/api/homework-types")
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.code === 0) {
              sel.innerHTML = '<option value="0">全部种类</option>';
              for (var i = 0; i < data.data.length; i++) {
                sel.innerHTML += '<option value="' + data.data[i].id + '">' + data.data[i].name + '</option>';
              }
            }
          })
          .catch(function () {});
      }
    }

    populateTypes();

    // 监听变化
    sel.addEventListener("change", function () {
      var hwTypeId = parseInt(this.value) || 0;
      // 更新全局 State
      if (window.State) {
        window.State.currentHomeworkTypeId = hwTypeId;
      }
      // 重新加载建议
      loadSuggestions();
    });

    // 当切换到 AI 助手 tab 时刷新选项（可能在别的 tab 修改了作业种类）
    var aiChatSection = document.getElementById("tabAIChat");
    if (aiChatSection) {
      var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (m) {
          if (m.target.classList.contains("active")) {
            populateTypes();
          }
        });
      });
      observer.observe(aiChatSection, { attributes: true, attributeFilter: ["class"] });
    }
  }

  // ---- Tab: AI 对话 ----
  function setupAIChatTab() {
    var input = document.getElementById("aiChatInput");
    var sendBtn = document.getElementById("btnAISend");
    if (!input || !sendBtn) return;

    // ---- 作业种类选择器 ----
    setupHomeworkTypeSelector();

    // ---- 考试 Excel 上传 ----
    setupExamUpload();

    async function sendMessage(question) {
      if (!question) return;
      input.value = "";
      input.disabled = true;
      sendBtn.disabled = true;

      addChatMessage("user", question);
      var loadingId = addLoadingMessage();

      var reqBody = { question: question };
      var cid = getCurrentClassId();
      if (cid > 0) reqBody.class_id = cid;
      var hwTypeId = getCurrentHomeworkTypeId();
      if (hwTypeId > 0) reqBody.homework_type_id = hwTypeId;

      try {
        var resp = await fetch("/api/ai/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(reqBody),
        });
        var data = await resp.json();
        removeLoadingMessage(loadingId);

        if (data.code === 0) {
          addChatMessage("ai", data.data.reply);

          // 保存 export_data 供导出使用
          AIState.lastExportData = data.data.export_data || null;
          AIState.lastReply = data.data.reply || "";
          AIState.lastVizHTML = data.data.viz_html || null;

          // 优先使用 LLM 生成的 HTML 可视化面板
          if (data.data.viz_html) {
            renderVizHTML(data.data.viz_html);
          } else if (data.data.chart) {
            renderAIChat(data.data.chart);
          }

          // 显示追问建议
          if (data.data.follow_ups && data.data.follow_ups.length > 0) {
            renderFollowUps(data.data.follow_ups);
          }

          // 显示导出按钮
          renderExportButtons();
        } else {
          addChatMessage("ai", "❌ " + data.msg + "\n\n> 💡 提示：请先在「⚙️ 设置」中配置 AI 服务。");
        }
      } catch (e) {
        removeLoadingMessage(loadingId);
        addChatMessage("ai", "❌ 网络请求失败，请检查网络连接。");
      }

      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();

      // 每次对话后刷新建议
      loadSuggestions();
    }

    sendBtn.addEventListener("click", function () {
      sendMessage(input.value.trim());
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(input.value.trim());
      }
    });

    // 动态加载提问建议
    loadSuggestions();
    // 每次切换到 AI 助手 tab 时刷新建议
    var aiChatSection = document.getElementById("tabAIChat");
    if (aiChatSection) {
      var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (m) {
          if (m.target.classList.contains("active")) {
            loadSuggestions();
          }
        });
      });
      observer.observe(aiChatSection, { attributes: true, attributeFilter: ["class"] });
    }
  }

  function addChatMessage(role, text) {
    var container = document.getElementById("aiChatMessages");
    if (!container) return;
    var div = document.createElement("div");
    div.className = "ai-msg ai-msg-" + role;
    var html = text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/^### (.+)$/gm, "<h4>$1</h4>")
      .replace(/^## (.+)$/gm, "<h3>$1</h3>")
      .replace(/^# (.+)$/gm, "<h2>$1</h2>")
      .replace(/^- (.+)$/gm, "<li>$1</li>")
      .replace(/^(\d+)\. (.+)$/gm, "<li>$2</li>")
      .replace(/\n\n/g, "</p><p>")
      .replace(/\n/g, "<br>");
    div.innerHTML = "<p>" + html + "</p>";
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  function addLoadingMessage() {
    var container = document.getElementById("aiChatMessages");
    if (!container) return "";
    var id = "loading-" + Date.now();
    var div = document.createElement("div");
    div.className = "ai-msg-loading";
    div.id = id;
    div.innerHTML = "<span></span><span></span><span></span>";
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return id;
  }

  function removeLoadingMessage(id) {
    var el = document.getElementById(id);
    if (el) el.remove();
  }

  // ---- HTML 可视化面板渲染（iframe 沙箱） ----
  function renderVizHTML(vizHTML) {
    var frame = document.getElementById("aiVizFrame");
    var placeholder = document.getElementById("aiChartPlaceholder");
    var chartBody = document.getElementById("aiChartBody");

    if (!frame || !chartBody) return;

    // 销毁旧的 ECharts 实例
    if (AIState.currentChart) {
      try { AIState.currentChart.dispose(); } catch (e) { /* ignore */ }
      AIState.currentChart = null;
    }

    // 清除 chartBody 中的非 iframe 内容
    var children = chartBody.children;
    for (var i = children.length - 1; i >= 0; i--) {
      if (children[i] !== frame) chartBody.removeChild(children[i]);
    }

    // 构建完整的 HTML 文档
    // 关键修复：在 vizHTML 之前同步获取 parent.echarts，
    // 避免 LLM 生成的 window.onload 在 echarts 就绪前被浏览器 load 事件触发
    var fullDoc = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n' +
      '<meta charset="UTF-8">\n' +
      // CSP：阻止 iframe 内加载外部 CDN 脚本（离线桌面应用无法访问外网，会挂起页面）
      // 注意：仅阻止外部脚本，不阻止 inline script/style
      '<meta http-equiv="Content-Security-Policy" content="script-src \'self\' \'unsafe-inline\' \'unsafe-eval\'; style-src \'self\' \'unsafe-inline\';">\n' +
      '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n' +
      '<style>\n' +
      '* { margin: 0; padding: 0; box-sizing: border-box; }\n' +
      'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; ' +
      'background: #f8f6f5; color: #4a4543; padding: 16px; overflow-y: auto; }\n' +
      'body::-webkit-scrollbar { width: 4px; }\n' +
      'body::-webkit-scrollbar-thumb { background: #ccc; border-radius: 2px; }\n' +
      'table { border-collapse: collapse; width: 100%; font-size: 13px; }\n' +
      'th { background: #7EB5D6; color: #fff; padding: 8px 10px; text-align: left; font-weight: 600; }\n' +
      'td { padding: 7px 10px; border-bottom: 1px solid #eee; }\n' +
      'tr:hover td { background: #f0f7fb; }\n' +
      '<\/style>\n' +
      '</head>\n<body>\n' +
      '<script>\n' +
      // 同步注入：在任何 LLM 脚本之前将 parent.echarts 复制到 iframe 全局
      // 不立即派发事件 — 等 DOM 解析完成后，通过原生 DOMContentLoaded 触发 echartsReady
      'window._ctErrors = [];\n' +
      'window.addEventListener("error", function(e) {\n' +
      '  window._ctErrors.push((e.message||"") + " @ " + (e.filename||"inline") + ":" + (e.lineno||""));\n' +
      '  if (parent && parent.console) parent.console.error("[AI-Viz]", e.message);\n' +
      '});\n' +
      'try {\n' +
      '  if (parent && parent.echarts) window.echarts = parent.echarts;\n' +
      '} catch(_) {}\n' +
      // ★ 关键：监听原生 DOMContentLoaded，此时 LLM 的所有 <script> 已注册完监听器
      // 然后派发 echartsReady，LLM 的方式1（推荐的 addEventListener('echartsReady')）就能触发
      'document.addEventListener("DOMContentLoaded", function() {\n' +
      '  if (typeof echarts !== "undefined") {\n' +
      '    window.dispatchEvent(new Event("echartsReady"));\n' +
      '  }\n' +
      '});\n' +
      // 兜底：如果同步注入失败（极端跨源场景），轮询等待 parent onload 注入
      'if (typeof echarts === "undefined") {\n' +
      '  var __t = 0, __fired = false;\n' +
      '  var __id = setInterval(function() {\n' +
      '    if (typeof echarts !== "undefined" && !__fired) {\n' +
      '      __fired = true; clearInterval(__id);\n' +
      '      window.dispatchEvent(new Event("echartsReady"));\n' +
      '      window.dispatchEvent(new Event("load"));\n' +
      '      if (typeof window.onload === "function") try { window.onload(); } catch(_) {}\n' +
      '    }\n' +
      '    if (++__t > 120) { clearInterval(__id); console.warn("ECharts unavailable"); }\n' +
      '  }, 50);\n' +
      '}\n' +
      '<\/script>\n' +
      '<div id="viz-root">\n' +
      vizHTML +
      '\n</div>\n' +
      '</body>\n</html>';

    // 使用 Blob URL 加载，确保 echarts 注入时机正确
    // 先移除旧 URL
    if (frame._blobUrl) {
      try { URL.revokeObjectURL(frame._blobUrl); } catch (e) { /* ignore */ }
    }
    var blob = new Blob([fullDoc], { type: "text/html" });
    var blobUrl = URL.createObjectURL(blob);
    frame._blobUrl = blobUrl;

    // 显示 iframe，隐藏占位符
    frame.style.display = "block";
    if (placeholder) placeholder.style.display = "none";

    // 更新标题
    var header = document.querySelector(".ai-chart-header");
    if (header) header.textContent = "📊 数据可视化";

    // onload 中注入 echarts（作为兜底，确保轮询方案能找到）
    frame.onload = function () {
      var iframeWin = frame.contentWindow;
      if (iframeWin && typeof echarts !== "undefined") {
        try {
          iframeWin.echarts = echarts;
        } catch (e) { /* ignore */ }
      }
      // 清理 Blob URL（延迟清理以确保 iframe 已加载）
      setTimeout(function () {
        if (frame._blobUrl) {
          try { URL.revokeObjectURL(frame._blobUrl); } catch (e) { /* ignore */ }
          frame._blobUrl = null;
        }
      }, 1000);
    };

    frame.src = blobUrl;
  }

  // ---- 追问建议渲染 ----
  function renderFollowUps(followUps) {
    var container = document.getElementById("aiChatMessages");
    if (!container) return;

    // 移除旧的追问
    var old = container.querySelector(".ai-follow-ups");
    if (old) old.remove();

    var div = document.createElement("div");
    div.className = "ai-follow-ups";
    div.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;padding:0 16px 10px 16px;align-self:flex-start;max-width:90%";

    var label = document.createElement("span");
    label.style.cssText = "font-size:.75rem;color:var(--text-lighter);width:100%;margin-bottom:2px";
    label.textContent = "💬 你可能还想问：";
    div.appendChild(label);

    for (var i = 0; i < followUps.length; i++) {
      (function (f) {
        var chip = document.createElement("button");
        chip.className = "ai-quick-btn";
        chip.style.cssText = "font-size:.78rem;padding:5px 10px;border-radius:12px;cursor:pointer";
        chip.textContent = (f.icon || "") + " " + f.text;
        chip.addEventListener("click", function () {
          var input = document.getElementById("aiChatInput");
          var sendBtn = document.getElementById("btnAISend");
          if (input && sendBtn) {
            input.value = f.text;
            sendBtn.click();
          }
        });
        div.appendChild(chip);
      })(followUps[i]);
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  // ---- 导出按钮渲染 ----
  function renderExportButtons() {
    var chartBody = document.getElementById("aiChartBody");
    if (!chartBody) return;

    // 移除旧按钮
    var old = chartBody.querySelector(".ai-export-bar");
    if (old) old.remove();

    var bar = document.createElement("div");
    bar.className = "ai-export-bar";
    bar.style.cssText = "display:flex;gap:6px;padding:8px 12px;justify-content:flex-end;" +
      "border-top:1px solid rgba(200,190,185,0.12);background:rgba(255,255,255,0.3);position:absolute;bottom:0;left:0;right:0;z-index:10";

    var excelBtn = document.createElement("button");
    excelBtn.className = "btn btn-sm btn-export";
    excelBtn.style.cssText = "font-size:.75rem;padding:4px 10px";
    excelBtn.innerHTML = "📥 导出Excel";
    excelBtn.addEventListener("click", async function () {
      if (!AIState.lastExportData) return;
      excelBtn.disabled = true;
      excelBtn.textContent = "⏳ 生成中...";
      try {
        var resp = await fetch("/api/ai/export/excel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            export_data: AIState.lastExportData,
            title: "AI分析报告",
          }),
        });
        if (resp.ok) {
          var blob = await resp.blob();
          var url = URL.createObjectURL(blob);
          var a = document.createElement("a");
          a.href = url;
          a.download = "AI分析报告.xlsx";
          a.click();
          URL.revokeObjectURL(url);
          if (typeof showToast === "function") showToast("✅ Excel 已下载");
        }
      } catch (e) {
        if (typeof showToast === "function") showToast("❌ 导出失败");
      }
      excelBtn.disabled = false;
      excelBtn.textContent = "📥 导出Excel";
    });

    var wordBtn = document.createElement("button");
    wordBtn.className = "btn btn-sm btn-export";
    wordBtn.style.cssText = "font-size:.75rem;padding:4px 10px";
    wordBtn.innerHTML = "📄 导出Word";
    wordBtn.addEventListener("click", async function () {
      if (!AIState.lastExportData) return;
      wordBtn.disabled = true;
      wordBtn.textContent = "⏳ 生成中...";
      try {
        var resp = await fetch("/api/ai/export/word", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            export_data: AIState.lastExportData,
            reply: AIState.lastReply || "",
            viz_html: AIState.lastVizHTML || "",
          }),
        });
        if (resp.ok) {
          var blob = await resp.blob();
          var url = URL.createObjectURL(blob);
          var a = document.createElement("a");
          a.href = url;
          a.download = "AI分析报告.doc";
          a.click();
          URL.revokeObjectURL(url);
          if (typeof showToast === "function") showToast("✅ Word 已下载");
        }
      } catch (e) {
        if (typeof showToast === "function") showToast("❌ 导出失败");
      }
      wordBtn.disabled = false;
      wordBtn.textContent = "📄 导出Word";
    });

    bar.appendChild(excelBtn);
    bar.appendChild(wordBtn);
    chartBody.style.position = "relative";
    chartBody.appendChild(bar);
  }

  // ---- ECharts 渲染（兜底方案：当 LLM 未生成 HTML 时使用） ----
  function renderAIChat(chartSpec) {
    var body = document.getElementById("aiChartBody");
    var frame = document.getElementById("aiVizFrame");
    var placeholder = document.getElementById("aiChartPlaceholder");
    if (!body) return;

    // 隐藏 iframe，使用直接 ECharts 渲染
    if (frame) frame.style.display = "none";
    if (placeholder) placeholder.style.display = "none";

    if (typeof echarts === "undefined") {
      if (placeholder) { placeholder.style.display = "flex"; }
      return;
    }

    // 更新图表标题
    var header = document.querySelector(".ai-chart-header");
    if (header && chartSpec.title) {
      header.textContent = "📊 " + chartSpec.title;
    }

    // 清除旧内容（保留 iframe 元素）
    var children = body.children;
    for (var i = children.length - 1; i >= 0; i--) {
      if (children[i] !== frame) body.removeChild(children[i]);
    }

    var chartDom = document.createElement("div");
    chartDom.style.width = "100%";
    chartDom.style.height = "100%";
    body.appendChild(chartDom);

    if (AIState.currentChart) {
      try { AIState.currentChart.dispose(); } catch (e) { /* ignore */ }
      AIState.currentChart = null;
    }

    try {
      var chart = echarts.init(chartDom);
      AIState.currentChart = chart;
      var option = chartSpec.option || buildDefaultChartOption(chartSpec);
      if (!option.tooltip) {
        option.tooltip = { trigger: chartSpec.type === "pie" ? "item" : "axis" };
      }
      chart.setOption(option, true);

      chart.off("click");
      chart.on("click", function (params) {
        var question = "";
        var chartType = chartSpec.type || "bar";
        if (chartType === "pie") {
          question = "哪些学生的等级是" + params.name + "？";
        } else if (chartType === "bar") {
          question = params.name ? ("查看" + params.name + "的详细情况") : "";
        } else if (chartType === "line" && params.name) {
          question = params.name + "那天各组的作业情况是怎样的？";
        }
        if (question) {
          var input = document.getElementById("aiChatInput");
          var sendBtn = document.getElementById("btnAISend");
          if (input && sendBtn) { input.value = question; sendBtn.click(); }
        }
      });

      var resizeHandler = function () {
        try { if (AIState.currentChart) AIState.currentChart.resize(); } catch (e) { /* ignore */ }
      };
      window.removeEventListener("resize", resizeHandler);
      window.addEventListener("resize", resizeHandler);
    } catch (e) {
      console.error("ECharts render failed:", e.message);
    }
  }

  function buildDefaultChartOption(spec) {
    // 本地兜底：当服务端返回的 option 为空时使用
    var macaronColors = ["#7EB5D6", "#E8A0BF", "#A8D5BA", "#F4C97E", "#C4B5D6", "#F0B8A0", "#8EC8C0", "#D4A8C8"];
    var type = spec.type || "bar";
    var title = spec.title || "";

    return {
      title: { text: title, left: "center", top: 10, textStyle: { fontSize: 15, fontWeight: "bold", color: "#5D5A5A" } },
      tooltip: { trigger: type === "pie" ? "item" : "axis" },
      color: macaronColors,
      grid: type !== "pie" ? { left: "3%", right: "5%", bottom: "8%", top: "15%", containLabel: true } : undefined,
      animation: true,
      animationDuration: 800,
    };
  }

  // ============================================================
  // 预警横幅
  // ============================================================
  function setupAlertBanner() {
    loadAlerts();
    setInterval(loadAlerts, 5 * 60 * 1000);
  }

  async function loadAlerts() {
    try {
      var resp = await fetch("/api/ai/alerts");
      var data = await resp.json();
      if (data.code === 0 && data.data && data.data.has_alerts) {
        AIState.alerts = data.data.alerts;
        renderAlertBanner(data.data.alerts);
      } else {
        hideAlertBanner();
      }
    } catch (e) {
      console.log("Alert load failed:", e.message);
    }
  }

  function renderAlertBanner(alerts) {
    var container = document.getElementById("alertBanner");
    if (!container) return;
    container.innerHTML = "";
    container.style.display = "block";

    for (var i = 0; i < alerts.length; i++) {
      var alert = alerts[i];
      var levelClass = alert.level === "danger" ? "alert-banner-danger" : "alert-banner-warning";
      var icon = alert.level === "danger" ? "🔴" : "🟠";

      var wrapper = document.createElement("div");
      wrapper.className = "alert-banner " + levelClass;

      var item = document.createElement("div");
      item.className = "alert-banner-item";
      item.innerHTML =
        '<span class="alert-icon">' + icon + "</span>" +
        '<div class="alert-content">' +
        '<div class="alert-title">' + alert.title + "</div>" +
        '<div class="alert-detail">' + alert.detail + "</div>" +
        "</div>" +
        '<span class="alert-action">点击查看详情 →</span>';

      (function (a) {
        item.addEventListener("click", function () {
          if (a.type === "consecutive_missing") {
            showConsecutiveMissingDetail(a.students);
          } else if (a.type === "a_rate_drop") {
            if (typeof switchTab === "function") switchTab("analytics");
            if (typeof showToast === "function") showToast("📉 A率下降详情：" + a.detail);
          }
        });
      })(alert);

      wrapper.appendChild(item);
      container.appendChild(wrapper);
    }
  }

  function hideAlertBanner() {
    var container = document.getElementById("alertBanner");
    if (container) container.style.display = "none";
  }

  function showConsecutiveMissingDetail(students) {
    var modal = document.getElementById("detailModal");
    var title = document.getElementById("detailModalTitle");
    var summary = document.getElementById("detailSummary");
    var list = document.getElementById("detailList");
    if (!modal || !title || !list) return;

    title.textContent = "⚠️ 连续未交学生名单";
    summary.innerHTML =
      '<span style="color:#c0392b;font-weight:600">共 ' + students.length + " 名学生连续3天以上未交作业</span>";

    var html = "";
    for (var i = 0; i < students.length; i++) {
      var s = students[i];
      html +=
        '<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 12px;border-radius:8px;margin-bottom:6px;background:rgba(231,76,60,0.06);border:1px solid rgba(231,76,60,0.12)">' +
        "<div><strong>" + s.student_name + "</strong>" +
        '<span style="color:var(--text-light);font-size:.8rem;margin-left:8px">' + s.group_name + "</span></div>" +
        '<span style="color:#c0392b;font-weight:600;font-size:.85rem">连续 ' + s.consecutive_days + " 天未交</span>" +
        "</div>";
    }
    list.innerHTML = html;
    modal.style.display = "flex";
  }

  // ============================================================
  // AI 评语按钮
  // ============================================================
  function setupAICommentButton() {
    var select = document.getElementById("exportStudentSelect");
    var btn = document.getElementById("btnAIGenerateComment");
    if (!select || !btn) return;

    btn.addEventListener("click", async function () {
      var sid = select.value;
      if (!sid) {
        if (typeof showToast === "function") showToast("⚠️ 请先选择一名学生");
        return;
      }
      btn.disabled = true;
      btn.textContent = "⏳ 生成中...";
      try {
        var resp = await fetch("/api/ai/comment/" + sid);
        var data = await resp.json();
        if (data.code === 0) {
          showCommentModal(data.data);
        } else {
          if (typeof showToast === "function") showToast("❌ " + data.msg);
        }
      } catch (e) {
        if (typeof showToast === "function") showToast("❌ 网络请求失败");
      }
      btn.disabled = false;
      btn.textContent = "🤖 AI 生成评语";
    });
  }

  function showCommentModal(commentData) {
    var modal = document.getElementById("commentModal");
    if (!modal) {
      modal = document.createElement("div");
      modal.className = "modal-overlay comment-modal";
      modal.id = "commentModal";
      modal.innerHTML =
        '<div class="modal-card">' +
        '<div class="modal-header"><h3>🤖 AI 评语</h3><button class="modal-close" id="btnCommentClose">✕</button></div>' +
        '<div class="modal-body">' +
        '<div class="comment-stats" id="commentStats"></div>' +
        '<div class="comment-content" id="commentContent"></div>' +
        '<div style="margin-top:12px;display:flex;gap:8px"><button class="btn btn-export btn-sm" id="btnCopyComment">📋 复制评语</button></div>' +
        "</div></div>";
      document.body.appendChild(modal);

      modal.querySelector("#btnCommentClose").addEventListener("click", function () {
        modal.style.display = "none";
      });
      modal.addEventListener("click", function (e) {
        if (e.target === modal) modal.style.display = "none";
      });
    }

    var statsEl = modal.querySelector("#commentStats");
    var contentEl = modal.querySelector("#commentContent");
    var stats = commentData.stats;

    var statsHtml = "";
    statsHtml += '<div class="comment-stat"><strong>' + commentData.student_name + "</strong></div>";
    statsHtml += '<div class="comment-stat">📝 共 ' + stats.total + " 次</div>";
    statsHtml += '<div class="comment-stat">⭐ A率 ' + stats.a_rate + "%</div>";
    statsHtml += '<div class="comment-stat">✅ 提交率 ' + stats.submit_rate + "%</div>";
    if (stats.consecutive_x >= 2) {
      statsHtml +=
        '<div class="comment-stat" style="color:#c0392b">⚠️ 连续' + stats.consecutive_x + "天未交</div>";
    }
    statsEl.innerHTML = statsHtml;
    contentEl.textContent = commentData.comment;

    modal.querySelector("#btnCopyComment").onclick = function () {
      navigator.clipboard.writeText(commentData.comment).then(
        function () {
          if (typeof showToast === "function") showToast("📋 评语已复制到剪贴板");
        },
        function () {
          if (typeof showToast === "function") showToast("⚠️ 复制失败，请手动复制");
        }
      );
    };

    modal.style.display = "flex";
  }

  // ============================================================
  // 智能分组按钮
  // ============================================================
  function setupSmartGroupButton() {
    var btn = document.getElementById("btnSmartGroup");
    if (!btn) return;
    btn.addEventListener("click", function () {
      showSmartGroupModal();
    });
  }

  function showSmartGroupModal() {
    var modal = document.getElementById("smartGroupModal");
    if (!modal) {
      modal = document.createElement("div");
      modal.className = "modal-overlay";
      modal.id = "smartGroupModal";
      modal.innerHTML =
        '<div class="modal-card modal-wide">' +
        '<div class="modal-header"><h3>🧠 AI 智能分组</h3><button class="modal-close" id="btnSmartGroupClose">✕</button></div>' +
        '<div class="modal-body">' +
        '<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">' +
        '<span class="control-label">分组数量：</span>' +
        '<input type="number" id="smartGroupCount" class="count-input" min="2" max="20" value="6" style="width:80px">' +
        '<button class="btn btn-export" id="btnSmartGroupPreview">🔍 预览分组</button></div>' +
        '<div class="smart-group-preview" id="smartGroupPreview">' +
        '<div style="text-align:center;color:var(--text-lighter);padding:30px">' +
        '<span style="font-size:2rem">🧠</span><p>点击「预览分组」查看 AI 均衡分组结果</p>' +
        '<p style="font-size:.78rem">基于近30天作业等级自动均衡</p></div></div>' +
        '<div style="margin-top:16px;display:flex;gap:8px" id="smartGroupActions" hidden>' +
        '<button class="btn btn-primary" id="btnSmartGroupApply">✅ 应用分组</button>' +
        '<button class="btn btn-outline" id="btnSmartGroupCancel">取消</button>' +
        '<span style="font-size:.78rem;color:var(--text-light);margin-left:auto;display:flex;align-items:center" id="smartGroupBalance"></span>' +
        "</div></div></div>";
      document.body.appendChild(modal);

      modal.querySelector("#btnSmartGroupClose").addEventListener("click", function () {
        modal.style.display = "none";
      });
      modal.addEventListener("click", function (e) {
        if (e.target === modal) modal.style.display = "none";
      });

      modal.querySelector("#btnSmartGroupPreview").addEventListener("click", async function () {
        var countEl = document.getElementById("smartGroupCount");
        var count = parseInt(countEl ? countEl.value : "6") || 6;
        var previewBtn = modal.querySelector("#btnSmartGroupPreview");
        previewBtn.disabled = true;
        previewBtn.textContent = "⏳ 计算中...";
        try {
          var resp = await fetch("/api/ai/smart-groups", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ group_count: count }),
          });
          var data = await resp.json();
          if (data.code === 0) {
            AIState.smartGroupResult = data.data;
            renderSmartGroupPreview(data.data);
            modal.querySelector("#smartGroupActions").hidden = false;
            var balEl = modal.querySelector("#smartGroupBalance");
            if (balEl) balEl.textContent = "⚖️ 均衡度: " + data.data.balance_score + "（越小越均衡）";
          } else {
            if (typeof showToast === "function") showToast("❌ " + data.msg);
          }
        } catch (e) {
          if (typeof showToast === "function") showToast("❌ 网络请求失败");
        }
        previewBtn.disabled = false;
        previewBtn.textContent = "🔍 预览分组";
      });

      modal.querySelector("#btnSmartGroupApply").addEventListener("click", async function () {
        if (!AIState.smartGroupResult) return;
        var applyBtn = modal.querySelector("#btnSmartGroupApply");
        applyBtn.disabled = true;
        applyBtn.textContent = "⏳ 应用中...";
        try {
          // 用 API.post 而不是裸 fetch：POST 会让前端 30 秒 GET 缓存失效，
          // 否则应用后 loadGroups 可能拿到旧分组数据
          var data = await API.post("/api/ai/smart-groups/apply", {
            groups: AIState.smartGroupResult.groups
          });
          if (data.code === 0) {
            if (typeof showToast === "function") showToast("✅ AI 智能分组已应用");
            modal.style.display = "none";
            // 应用分组后所有分组 ID 已重建，必须整页重载数据（含学生），
            // 只调 loadGroups 会导致 State.students 里的旧 group_id 与新分组
            // 对不上，学生名单从页面上"消失"
            if (typeof loadAllData === "function") await loadAllData();
          } else {
            if (typeof showToast === "function") showToast("❌ " + data.msg);
          }
        } catch (e) {
          if (typeof showToast === "function") showToast("❌ 应用失败");
        }
        applyBtn.disabled = false;
        applyBtn.textContent = "✅ 应用分组";
      });

      modal.querySelector("#btnSmartGroupCancel").addEventListener("click", function () {
        modal.style.display = "none";
      });
    }
    modal.style.display = "flex";
  }

  function renderSmartGroupPreview(data) {
    var container = document.getElementById("smartGroupPreview");
    if (!container) return;
    var html = "";
    for (var i = 0; i < data.groups.length; i++) {
      var g = data.groups[i];
      html +=
        '<div class="smart-group-item">' +
        '<span class="smart-group-color" style="background:' + g.color + '"></span>' +
        '<span class="smart-group-name">' + g.name + "</span>" +
        '<span class="smart-group-info">' + g.student_count + "人 · 均分 " + g.avg_score + "</span>" +
        '<span class="smart-group-students">' + g.students.map(function (s) { return s.name; }).join("、") + "</span>" +
        "</div>";
    }
    container.innerHTML = html;
  }

  // ============================================================
  // 启动
  // ============================================================
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      setTimeout(safeInit, 300);
    });
  } else {
    // DOM 已加载，直接初始化
    setTimeout(safeInit, 300);
  }

  // ============================================================
  // 班级切换时重置 AI 上下文
  // ============================================================
  function resetAIContext() {
    // 清空聊天记录
    AIState.chatHistory = [];
    var messagesEl = document.getElementById("aiChatMessages");
    if (messagesEl) {
      messagesEl.innerHTML =
        '<div class="ai-msg ai-msg-ai">' +
        '<p>👋 你好！我是 ClassTrack AI 助手。<br>' +
        '已切换到新班级。我可以帮你分析班级作业数据、生成图表、识别趋势。<br>' +
        '试试下面的快捷提问，或直接输入你的问题吧！</p>' +
        '</div>';
    }

    // 清除图表
    var frame = document.getElementById("aiVizFrame");
    if (frame) {
      frame.style.display = "none";
      frame.srcdoc = "";
      if (frame._blobUrl) {
        try { URL.revokeObjectURL(frame._blobUrl); } catch (e) { /* ignore */ }
        frame._blobUrl = null;
      }
    }
    if (AIState.currentChart) {
      try { AIState.currentChart.dispose(); } catch (e) { /* ignore */ }
      AIState.currentChart = null;
    }
    var placeholder = document.getElementById("aiChartPlaceholder");
    if (placeholder) placeholder.style.display = "flex";
    var chartBody = document.getElementById("aiChartBody");
    if (chartBody) {
      var children = chartBody.children;
      for (var i = children.length - 1; i >= 0; i--) {
        if (children[i] !== frame) chartBody.removeChild(children[i]);
      }
    }
    // 移除旧导出按钮
    var oldBar = chartBody ? chartBody.querySelector(".ai-export-bar") : null;
    if (oldBar) oldBar.remove();

    // 清除导出数据
    AIState.lastExportData = null;
    AIState.lastReply = "";
    AIState.lastVizHTML = null;

    // 重新加载提问建议
    try { loadSuggestions(); } catch (e) { /* ignore */ }
  }
  window.resetAIContext = resetAIContext;
})();
