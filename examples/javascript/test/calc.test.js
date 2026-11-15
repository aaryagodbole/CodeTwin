import test from 'node:test';
import assert from 'node:assert';
import { add } from '../src/calc.js';

test('add', () => assert.strictEqual(add(1, 2), 3));
