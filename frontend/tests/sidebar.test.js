/**
 * 侧边栏模块测试
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { Sidebar, AppState, Auth } from './setup.js';

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  AppState.clearAll();
  document.body.innerHTML = `
    <aside id="sidebar" class="sidebar">
      <div class="sidebar-header">
        <h3 id="sidebar-display-name">用户</h3>
        <div class="username" id="sidebar-username">@username</div>
      </div>
      <div class="sidebar-body">
        <div class="sidebar-section">
          <details class="panel" id="panel-settings">
            <summary>个人设置</summary>
            <div class="panel-body">
              <button id="btn-refresh-profile">刷新信息</button>
              <div class="settings-form">
                <div class="form-row">
                  <label for="settings-display_name">昵称</label>
                  <input id="settings-display_name" value="">
                </div>
                <div class="form-row">
                  <label for="settings-email">邮箱</label>
                  <input id="settings-email" value="">
                </div>
                <div class="form-row">
                  <label for="settings-level">水平</label>
                  <select id="settings-level">
                    <option value="beginner">入门</option>
                    <option value="intermediate">中级</option>
                    <option value="advanced">高级</option>
                    <option value="expert">专家</option>
                  </select>
                </div>
                <div class="form-row">
                  <label for="settings-target_field">目标领域</label>
                  <input id="settings-target_field" value="">
                </div>
                <div class="form-row-inline">
                  <label for="settings-available_time">时间</label>
                  <span id="settings-time-value">10</span>
                </div>
                <input type="range" id="settings-available_time" min="1" max="80" value="10">
                <button id="btn-save-settings">保存设置</button>
              </div>
            </div>
          </details>
        </div>
        <div class="sidebar-section">
          <details class="panel" id="panel-password">
            <summary>修改密码</summary>
            <div class="panel-body">
              <input type="password" id="settings-old-password">
              <input type="password" id="settings-new-password">
              <input type="password" id="settings-new-password-confirm">
              <button id="btn-change-password">修改密码</button>
            </div>
          </details>
        </div>
        <div class="sidebar-section">
          <details class="panel" id="panel-agent" open>
            <summary>Agent 选择</summary>
            <div class="panel-body">
              <div class="agent-selector">
                <label class="radio-item checked">
                  <input type="radio" name="agent" value="auto" checked>
                </label>
                <label class="radio-item">
                  <input type="radio" name="agent" value="planner">
                </label>
                <label class="radio-item">
                  <input type="radio" name="agent" value="expert">
                </label>
                <label class="radio-item">
                  <input type="radio" name="agent" value="partner">
                </label>
                <label class="radio-item">
                  <input type="radio" name="agent" value="quizzer">
                </label>
                <label class="radio-item">
                  <input type="radio" name="agent" value="reviewer">
                </label>
                <label class="radio-item">
                  <input type="radio" name="agent" value="examiner">
                </label>
              </div>
            </div>
          </details>
        </div>
        <div class="sidebar-section">
          <button id="btn-quick-plan">计划</button>
          <button id="btn-logout">退出</button>
        </div>
        <div class="sidebar-section">
          <details class="panel" id="panel-quiz">
            <summary>测验</summary>
            <div class="panel-body">
              <input id="quiz-gen-topic" value="Python基础">
              <input type="range" id="quiz-gen-count" min="1" max="10" value="3">
              <span id="quiz-count-value">3</span>
              <button id="btn-generate-quiz">生成测验</button>
            </div>
          </details>
        </div>
      </div>
    </aside>
    <button id="sidebar-toggle">☰</button>
    <div id="sidebar-overlay"></div>
  `;
});

describe('Sidebar', () => {
  describe('init', () => {
    it('初始化侧边栏用户信息', () => {
      AppState.setDisplayName('测试用户');
      AppState.setUsername('testuser');
      Sidebar.init();
      expect(document.getElementById('sidebar-display-name').textContent).toBe('测试用户');
      expect(document.getElementById('sidebar-username').textContent).toBe('@testuser');
    });
  });

  describe('toggleSidebar', () => {
    it('切换侧边栏展开状态', () => {
      Sidebar.init();
      const sidebar = document.getElementById('sidebar');
      expect(sidebar.classList.contains('open')).toBe(true);
      Sidebar.toggleSidebar();
      expect(sidebar.classList.contains('open')).toBe(false);
      Sidebar.toggleSidebar();
      expect(sidebar.classList.contains('open')).toBe(true);
    });
  });

  describe('closeSidebar', () => {
    it('关闭侧边栏', () => {
      Sidebar.init();
      const sidebar = document.getElementById('sidebar');
      sidebar.classList.add('open');
      Sidebar.closeSidebar();
      expect(sidebar.classList.contains('open')).toBe(false);
    });
  });

  describe('syncAgentSelector', () => {
    it('同步 Agent 选择器状态', () => {
      Sidebar.init();
      Sidebar.syncAgentSelector('planner');
      const plannerRadio = document.querySelector('input[value="planner"]');
      expect(plannerRadio.checked).toBe(true);
    });

    it('auto 同步为 auto', () => {
      Sidebar.init();
      Sidebar.syncAgentSelector('');
      const autoRadio = document.querySelector('input[value="auto"]');
      expect(autoRadio.checked).toBe(true);
    });
  });

  describe('初始化 Agent 选择器', () => {
    it('默认选中当前 Agent', () => {
      AppState.setCurrentAgent('quizzer');
      Sidebar.init();
      const quizzerRadio = document.querySelector('input[value="quizzer"]');
      expect(quizzerRadio.checked).toBe(true);
    });

    it('切换 Agent 更新状态', () => {
      Sidebar.init();
      const expertRadio = document.querySelector('input[value="expert"]');
      expertRadio.click();
      expect(AppState.getCurrentAgent()).toBe('expert');
    });
  });

  describe('超级操作', () => {
    it('退出按钮存在', () => {
      Sidebar.init();
      const logoutBtn = document.getElementById('btn-logout');
      expect(logoutBtn).toBeTruthy();
    });

    it('计划按钮存在', () => {
      Sidebar.init();
      const planBtn = document.getElementById('btn-quick-plan');
      expect(planBtn).toBeTruthy();
    });

    it('生成测验按钮存在', () => {
      Sidebar.init();
      const quizBtn = document.getElementById('btn-generate-quiz');
      expect(quizBtn).toBeTruthy();
    });
  });
});