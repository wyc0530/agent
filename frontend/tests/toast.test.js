/**
 * Toast 消息提示模块测试
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { Toast } from './setup.js';

beforeEach(() => {
  // 不清理 DOM，因为 Toast 模块内部缓存了容器引用
  // 而是清理已有的 toast 元素
  const toasts = document.querySelectorAll('.toast');
  toasts.forEach(function (t) { t.remove(); });
});

describe('Toast', () => {
  describe('show', () => {
    it('显示一条 toast 消息', () => {
      Toast.show('测试消息', 'info', 0);
      const toast = document.querySelector('.toast');
      expect(toast).toBeTruthy();
      expect(toast.textContent).toContain('测试消息');
    });

    it('info 类型有对应 class', () => {
      Toast.show('消息', 'info', 0);
      const toast = document.querySelector('.toast');
      expect(toast).toBeTruthy();
      expect(toast.classList.contains('info')).toBe(true);
    });

    it('success 类型', () => {
      Toast.show('成功', 'success', 0);
      const toast = document.querySelector('.toast');
      expect(toast).toBeTruthy();
      expect(toast.classList.contains('success')).toBe(true);
    });

    it('error 类型', () => {
      Toast.show('错误', 'error', 0);
      const toast = document.querySelector('.toast');
      expect(toast).toBeTruthy();
      expect(toast.classList.contains('error')).toBe(true);
    });

    it('warning 类型', () => {
      Toast.show('警告', 'warning', 0);
      const toast = document.querySelector('.toast');
      expect(toast).toBeTruthy();
      expect(toast.classList.contains('warning')).toBe(true);
    });

    it('默认类型为 info', () => {
      Toast.show('默认', undefined, 0);
      const toast = document.querySelector('.toast');
      expect(toast).toBeTruthy();
      expect(toast.classList.contains('info')).toBe(true);
    });

    it('多条 toast 可同时显示', () => {
      Toast.show('第一条', 'info', 0);
      Toast.show('第二条', 'success', 0);
      const toasts = document.querySelectorAll('.toast');
      expect(toasts.length).toBe(2);
    });
  });
});