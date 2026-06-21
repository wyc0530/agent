/**
 * 侧边栏模块
 * 用户信息、个人设置、Agent 选择、快捷操作、测验生成
 */
var Sidebar = (function () {
  'use strict';

  var _sidebarEl = null;
  var _toggleBtn = null;
  var _closeBtn = null;
  var _overlayEl = null;

  /** 初始化侧边栏 */
  function init() {
    _sidebarEl = Utils.$('#sidebar');
    _toggleBtn = Utils.$('#sidebar-toggle');
    _closeBtn = Utils.$('#sidebar-close');
    _overlayEl = Utils.$('#sidebar-overlay');

    // 默认打开侧边栏
    if (_sidebarEl) {
      _sidebarEl.classList.add('open');
    }
    if (_toggleBtn) {
      _toggleBtn.setAttribute('aria-expanded', 'true');
      _toggleBtn.setAttribute('aria-label', '收起侧边栏');
    }

    // 汉堡菜单切换
    if (_toggleBtn) {
      _toggleBtn.addEventListener('click', openSidebar);
    }
    if (_closeBtn) {
      _closeBtn.addEventListener('click', closeSidebar);
    }
    if (_overlayEl) {
      _overlayEl.addEventListener('click', closeSidebar);
    }

    // 初始化各面板
    initUserInfo();
    initSettings();
    initPasswordChange();
    initAgentSelector();
    initQuickActions();
    initQuizGenerator();

    // 初始化历史对话
    if (typeof Conversations !== 'undefined') {
      Conversations.init();
    }
  }

  /** 打开侧边栏 */
  function openSidebar() {
    if (!_sidebarEl) return;
    _sidebarEl.classList.add('open');
    if (_overlayEl) _overlayEl.classList.add('open');
    if (_toggleBtn) {
      _toggleBtn.setAttribute('aria-expanded', 'true');
      _toggleBtn.setAttribute('aria-label', '收起侧边栏');
    }
  }

  /** 切换侧边栏 */
  function toggleSidebar() {
    if (!_sidebarEl) return;
    var isOpen = _sidebarEl.classList.contains('open');
    if (isOpen) {
      closeSidebar();
    } else {
      openSidebar();
    }
  }

  /** 关闭侧边栏 */
  function closeSidebar() {
    if (_sidebarEl) _sidebarEl.classList.remove('open');
    if (_overlayEl) _overlayEl.classList.remove('open');
    if (_toggleBtn) {
      _toggleBtn.setAttribute('aria-expanded', 'false');
      _toggleBtn.setAttribute('aria-label', '展开侧边栏');
    }
  }

  /** 初始化用户信息 */
  function initUserInfo() {
    var displayName = AppState.getDisplayName();
    var username = AppState.getUsername();
    var nameEl = Utils.$('#sidebar-display-name');
    var userEl = Utils.$('#sidebar-username');
    if (nameEl) nameEl.textContent = displayName;
    if (userEl) userEl.textContent = '@' + username;
  }

  /** 初始化个人设置 */
  function initSettings() {
    var profile = AppState.getProfile();

    // 填充已有数据
    ['display_name', 'email', 'level', 'target_field', 'available_time'].forEach(function (key) {
      var el = Utils.$('#settings-' + key);
      if (el && profile[key] !== undefined) {
        el.value = profile[key];
      }
    });

    // 刷新按钮
    var refreshBtn = Utils.$('#btn-refresh-profile');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', function () {
        ApiClient.getProfile()
          .then(function (data) {
            AppState.setProfile(data);
            ['display_name', 'email', 'level', 'target_field', 'available_time'].forEach(function (key) {
              var el = Utils.$('#settings-' + key);
              if (el && data[key] !== undefined) {
                el.value = data[key];
              }
            });
            Toast.show('信息已刷新', 'success');
          })
          .catch(function () {
            Toast.show('获取信息失败', 'error');
          });
      });
    }

    // 保存按钮
    var saveBtn = Utils.$('#btn-save-settings');
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        var profileData = {};
        ['display_name', 'email', 'level', 'target_field'].forEach(function (key) {
          var el = Utils.$('#settings-' + key);
          if (el) profileData[key] = el.value;
        });
        var timeEl = Utils.$('#settings-available_time');
        if (timeEl) profileData.available_time = parseInt(timeEl.value, 10) || 10;

        ApiClient.updateProfile(profileData)
          .then(function (data) {
            AppState.setProfile(data);
            if (data.display_name) {
              AppState.setDisplayName(data.display_name);
              initUserInfo();
            }
            Toast.show('已保存', 'success');
          })
          .catch(function (err) {
            Toast.show(err.message || '保存失败', 'error');
          });
      });
    }

    // 可用时间滑块显示
    var timeSlider = Utils.$('#settings-available_time');
    var timeVal = Utils.$('#settings-time-value');
    if (timeSlider && timeVal) {
      timeVal.textContent = timeSlider.value;
      timeSlider.addEventListener('input', function () {
        timeVal.textContent = this.value;
      });
    }
  }

  /** 初始化密码修改 */
  function initPasswordChange() {
    var btn = Utils.$('#btn-change-password');
    if (btn) {
      btn.addEventListener('click', Auth.handlePasswordChange);
    }
  }

  /** 初始化 Agent 选择器 */
  function initAgentSelector() {
    var currentAgent = AppState.getCurrentAgent() || 'auto';
    var radioBtns = Utils.$$('.agent-selector input[type="radio"]');
    radioBtns.forEach(function (radio) {
      if (radio.value === currentAgent) {
        radio.checked = true;
        radio.closest('.radio-item').classList.add('checked');
      }
      radio.addEventListener('change', function () {
        AppState.setCurrentAgent(this.value === 'auto' ? '' : this.value);
        radioBtns.forEach(function (r) {
          var item = r.closest('.radio-item');
          if (item) item.classList.toggle('checked', r.checked);
        });
      });
    });
  }

  /** 同步 Agent 选择器 */
  function syncAgentSelector(agentRole) {
    var radio = Utils.$('.agent-selector input[value="' + (agentRole || 'auto') + '"]');
    if (radio) {
      radio.checked = true;
      radio.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  /** 初始化快捷操作 */
  function initQuickActions() {
    var planBtn = Utils.$('#btn-quick-plan');
    if (planBtn) {
      planBtn.addEventListener('click', function () {
        var inputEl = Utils.$('#chat-input');
        if (inputEl) {
          inputEl.value = '帮我制定一个学习计划';
          inputEl.style.height = 'auto';
          AppState.setCurrentAgent('planner');
          syncAgentSelector('planner');
          Chat.sendMessage();
        }
      });
    }

    var logoutBtn = Utils.$('#btn-logout');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', Auth.showLogoutConfirm);
    }
  }

  /** 初始化测验生成器 */
  function initQuizGenerator() {
    var countSlider = Utils.$('#quiz-gen-count');
    var countVal = Utils.$('#quiz-count-value');
    if (countSlider && countVal) {
      countVal.textContent = countSlider.value;
      countSlider.addEventListener('input', function () {
        countVal.textContent = this.value;
      });
    }

    var generateBtn = Utils.$('#btn-generate-quiz');
    if (generateBtn) {
      generateBtn.addEventListener('click', function () {
        var topic = (Utils.$('#quiz-gen-topic') || {}).value || 'Python基础';
        var count = (Utils.$('#quiz-gen-count') || {}).value || '3';
        var inputEl = Utils.$('#chat-input');
        if (inputEl) {
          inputEl.value = '请为' + topic + '生成' + count + '道测试题';
          inputEl.style.height = 'auto';
          AppState.setCurrentAgent('quizzer');
          syncAgentSelector('quizzer');
          Chat.sendMessage();
        }
      });
    }
  }

  return {
    init: init,
    toggleSidebar: toggleSidebar,
    openSidebar: openSidebar,
    closeSidebar: closeSidebar,
    syncAgentSelector: syncAgentSelector,
  };
})();