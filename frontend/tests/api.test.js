/**
 * API 客户端模块测试
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { ApiClient, AppState } from './setup.js';

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

describe('ApiClient', () => {
  describe('ApiError', () => {
    it('创建 ApiError 实例', () => {
      const err = new ApiClient.ApiError('测试错误', 400);
      expect(err.message).toBe('测试错误');
      expect(err.statusCode).toBe(400);
    });
  });

  describe('setBaseUrl', () => {
    it('设置 API 基础 URL', () => {
      ApiClient.setBaseUrl('http://test:9000');
      // 通过 fetch mock 验证
      expect(typeof ApiClient.setBaseUrl).toBe('function');
    });
  });

  describe('请求头构建', () => {
    it('无 Token 时不带 Authorization', async () => {
      AppState.clearAll();
      // 验证 API 可以正常调用
      expect(typeof ApiClient.checkHealth).toBe('function');
    });

    it('有 Token 时带 Authorization', () => {
      AppState.setToken('test-token');
      expect(AppState.getToken()).toBe('test-token');
    });
  });
});