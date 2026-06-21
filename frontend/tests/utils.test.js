/**
 * 工具函数模块测试
 */
import { describe, it, expect } from 'vitest';
import { Utils } from './setup.js';

describe('Utils', () => {
  describe('escapeHtml', () => {
    it('转义 HTML 特殊字符', () => {
      const result = Utils.escapeHtml('<script>alert("xss")</script>');
      expect(result).not.toContain('<script>');
      expect(result).toContain('&lt;');
    });

    it('空字符串返回空', () => {
      expect(Utils.escapeHtml('')).toBe('');
    });

    it('null/undefined 返回空', () => {
      expect(Utils.escapeHtml(null)).toBe('');
      expect(Utils.escapeHtml(undefined)).toBe('');
    });
  });

  describe('表单校验', () => {
    it('validateRequired 空值返回错误', () => {
      expect(Utils.validateRequired('', '用户名')).toBe('用户名为必填项');
      expect(Utils.validateRequired('  ', '密码')).toBe('密码为必填项');
    });

    it('validateRequired 有值返回 null', () => {
      expect(Utils.validateRequired('hello', '用户名')).toBeNull();
    });

    it('validateMinLength 不足长度返回错误', () => {
      expect(Utils.validateMinLength('ab', 3, '用户名')).toBe('用户名至少3个字符');
    });

    it('validateMinLength 满足长度返回 null', () => {
      expect(Utils.validateMinLength('abc', 3, '用户名')).toBeNull();
    });

    it('validateEmail 正确格式', () => {
      expect(Utils.validateEmail('test@example.com')).toBeNull();
      expect(Utils.validateEmail('')).toBeNull();
    });

    it('validateEmail 错误格式', () => {
      expect(Utils.validateEmail('not-an-email')).toBe('邮箱格式不正确');
    });
  });

  describe('safeJsonParse', () => {
    it('解析有效 JSON', () => {
      expect(Utils.safeJsonParse('{"a":1}')).toEqual({ a: 1 });
    });

    it('解析无效 JSON 返回 fallback', () => {
      expect(Utils.safeJsonParse('invalid', null)).toBeNull();
      expect(Utils.safeJsonParse('invalid', [])).toEqual([]);
    });
  });

  describe('createEl', () => {
    it('创建带属性的元素', () => {
      const el = Utils.createEl('div', { className: 'test', id: 'my-id' });
      expect(el.tagName).toBe('DIV');
      expect(el.className).toBe('test');
      expect(el.id).toBe('my-id');
    });

    it('创建带文本内容的元素', () => {
      const el = Utils.createEl('span', { textContent: 'Hello' });
      expect(el.textContent).toBe('Hello');
    });

    it('创建带子元素的元素', () => {
      const child = Utils.createEl('span', { textContent: 'child' });
      const parent = Utils.createEl('div', {}, [child]);
      expect(parent.children).toHaveLength(1);
      expect(parent.children[0].textContent).toBe('child');
    });

    it('创建带事件监听器的元素', () => {
      let clicked = false;
      const el = Utils.createEl('button', { onClick: () => { clicked = true; } });
      el.click();
      expect(clicked).toBe(true);
    });
  });

  describe('防抖', () => {
    it('debounce 延迟执行', async () => {
      let count = 0;
      const fn = Utils.debounce(() => { count++; }, 50);
      fn();
      fn();
      fn();
      expect(count).toBe(0);
      await new Promise((r) => setTimeout(r, 80));
      expect(count).toBe(1);
    });
  });
});