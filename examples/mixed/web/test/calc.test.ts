import { expect, test } from 'vitest';
import { add } from '../src/calc';

test('add', () => expect(add(1, 2)).toBe(3));
