/**
 * SSE 解析模块测试
 */
import { describe, it, expect } from 'vitest';
import { SSE } from './setup.js';

describe('SSE', () => {
  describe('parseLine', () => {
    it('解析标准 SSE 数据行', () => {
      const result = SSE.parseLine('data: {"type":"chunk","content":"hello"}');
      expect(result).toEqual({ type: 'chunk', content: 'hello' });
    });

    it('空行返回 null', () => {
      expect(SSE.parseLine('')).toBeNull();
      expect(SSE.parseLine(null)).toBeNull();
    });

    it('非 data: 前缀返回 null', () => {
      expect(SSE.parseLine('event: message')).toBeNull();
    });

    it('解析 start 事件', () => {
      const result = SSE.parseLine('data: {"type":"start","agent_role":"planner"}');
      expect(result.type).toBe('start');
      expect(result.agent_role).toBe('planner');
    });

    it('解析 error 事件', () => {
      const result = SSE.parseLine('data: {"type":"error","content":"timeout"}');
      expect(result.type).toBe('error');
      expect(result.content).toBe('timeout');
    });

    it('解析无效 JSON 返回 null', () => {
      const result = SSE.parseLine('data: {invalid json}');
      expect(result).toBeNull();
    });
  });
});