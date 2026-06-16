/**
 * 认证模块测试
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { Auth } from './setup.js';

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  document.body.innerHTML = `
    <div class="auth-tabs">
      <button class="auth-tab active" data-tab="login">登录</button>
      <button class="auth-tab" data-tab="register">注册</button>
    </div>
    <form class="auth-form active" data-form="login">
      <input id="login-username" value="">
      <input id="login-password" value="">
      <button id="btn-login">登录</button>
    </form>
    <form class="auth-form" data-form="register">
      <input id="reg-username" value="">
      <input id="reg-display-name" value="">
      <input id="reg-email" value="">
      <input id="reg-password" value="">
      <input id="reg-password-confirm" value="">
      <button id="btn-register">注册</button>
    </form>
  `;
});

describe('Auth', () => {
  describe('initLoginPage', () => {
    it('初始化后 Tab 切换功能正常', () => {
      Auth.initLoginPage();
      const tabs = document.querySelectorAll('.auth-tab');
      expect(tabs.length).toBe(2);

      // 点击注册 tab
      const registerTab = document.querySelector('.auth-tab[data-tab="register"]');
      registerTab.click();
      expect(registerTab.classList.contains('active')).toBe(true);
      const loginForm = document.querySelector('.auth-form[data-form="login"]');
      const registerForm = document.querySelector('.auth-form[data-form="register"]');
      expect(registerForm.classList.contains('active')).toBe(true);
      expect(loginForm.classList.contains('active')).toBe(false);
    });
  });

  describe('handleLogin', () => {
    it('空用户名提示错误', () => {
      document.getElementById('login-username').value = '';
      document.getElementById('login-password').value = '';
      Auth.handleLogin();
      // 应该显示 toast 提示
      const toast = document.querySelector('.toast');
      expect(toast).toBeTruthy();
    });
  });

  describe('handleLogout', () => {
    it('退出登录清除状态', () => {
      // 先设置一些状态
      localStorage.setItem('ls_token', 'test-token');
      Auth.handleLogout();
      // 验证状态被清除
      expect(localStorage.getItem('ls_token')).toBeNull();
    });
  });
});