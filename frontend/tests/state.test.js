/**
 * 状态管理模块测试
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { AppState } from './setup.js';

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

describe('AppState', () => {
  describe('Token 管理', () => {
    it('初始状态 Token 为空', () => {
      expect(AppState.getToken()).toBe('');
    });

    it('设置和获取 Token', () => {
      AppState.setToken('test-token-123');
      expect(AppState.getToken()).toBe('test-token-123');
    });

    it('Token 存储在 localStorage', () => {
      AppState.setToken('persist-token');
      expect(localStorage.getItem('ls_token')).toBe('persist-token');
    });
  });

  describe('登录状态', () => {
    it('无 Token 时未登录', () => {
      expect(AppState.isLoggedIn()).toBe(false);
    });

    it('有 Token 时已登录', () => {
      AppState.setToken('valid-token');
      expect(AppState.isLoggedIn()).toBe(true);
    });

    it('applyLogin 设置完整登录状态', () => {
      AppState.applyLogin({
        token: 'auth-token',
        user_id: 'user-1',
        username: 'testuser',
        display_name: '测试用户',
      });
      expect(AppState.getToken()).toBe('auth-token');
      expect(AppState.getUserId()).toBe('user-1');
      expect(AppState.getUsername()).toBe('testuser');
      expect(AppState.getDisplayName()).toBe('测试用户');
    });

    it('applyLogin 无 display_name 时使用 username', () => {
      AppState.applyLogin({ token: 't', user_id: 'u', username: 'user' });
      expect(AppState.getDisplayName()).toBe('user');
    });
  });

  describe('消息管理', () => {
    it('初始消息为空数组', () => {
      expect(AppState.getMessages()).toEqual([]);
    });

    it('添加消息', () => {
      AppState.addMessage({ role: 'user', content: 'hello' });
      const msgs = AppState.getMessages();
      expect(msgs).toHaveLength(1);
      expect(msgs[0].content).toBe('hello');
    });

    it('消息超过50条时截断', () => {
      for (let i = 0; i < 60; i++) {
        AppState.addMessage({ role: 'user', content: 'msg' + i });
      }
      const msgs = AppState.getMessages();
      expect(msgs.length).toBeLessThanOrEqual(50);
      // 应该保留最新的消息
      expect(msgs[msgs.length - 1].content).toBe('msg59');
    });
  });

  describe('用户资料', () => {
    it('初始资料为空对象', () => {
      expect(AppState.getProfile()).toEqual({});
    });

    it('设置和获取资料', () => {
      AppState.setProfile({ level: 'intermediate', preference: 'visual' });
      expect(AppState.getProfile().level).toBe('intermediate');
    });
  });

  describe('Agent 选择', () => {
    it('初始 Agent 为空', () => {
      expect(AppState.getCurrentAgent()).toBe('');
    });

    it('设置和获取 Agent', () => {
      AppState.setCurrentAgent('planner');
      expect(AppState.getCurrentAgent()).toBe('planner');
    });
  });

  describe('退出登录', () => {
    it('clearAll 清除所有状态', () => {
      AppState.applyLogin({ token: 't', user_id: 'u', username: 'user' });
      AppState.setProfile({ level: 'beginner' });
      AppState.addMessage({ role: 'user', content: 'test' });
      AppState.setCurrentAgent('planner');

      AppState.clearAll();

      expect(AppState.getToken()).toBe('');
      expect(AppState.getUserId()).toBe('');
      expect(AppState.getMessages()).toEqual([]);
      expect(AppState.getProfile()).toEqual({});
      expect(AppState.getCurrentAgent()).toBe('');
    });
  });
});